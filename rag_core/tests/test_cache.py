"""Unit tests for rag_core caching behavior."""

import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag_core.core.cache import (
    QueryEmbeddingCache,
    RetrievalResultCache,
    query_embedding_cache,
    retrieval_result_cache,
    normalize_query,
)
from rag_core.core.embedding_defaults import EMBEDDING_DIMENSION
from rag_core.core.token_usage import TokenUsage
from rag_core.rag.embeddings import EmbeddingResult
from rag_core.rag.schemas import RetrievedChunk


def test_normalize_query_strips_and_lowercases_text() -> None:
    assert normalize_query("  Hello   WORLD  \n") == "hello world"


def test_query_embedding_cache_uses_normalized_keys_and_skips_api_calls() -> None:
    query_embedding_cache.clear()
    expected_vector = [0.5] * EMBEDDING_DIMENSION

    response = MagicMock()
    response.data = [MagicMock(index=0, embedding=expected_vector)]
    response.usage = MagicMock(prompt_tokens=1, total_tokens=1, completion_tokens=0)

    with patch("rag_core.rag.embeddings.create_embeddings", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = response
        from rag_core.rag.embeddings import embed_texts

        output1 = embed_texts(["Hello  world"])
        output2 = embed_texts(["hello world"])

    assert output1 == output2 == [expected_vector]
    assert mock_create.await_count == 1


def test_embed_texts_batch_partial_hit_only_calls_api_for_miss() -> None:
    query_embedding_cache.clear()

    expected_vector_a = [1.0] * EMBEDDING_DIMENSION
    expected_vector_b = [2.0] * EMBEDDING_DIMENSION
    expected_vector_c = [3.0] * EMBEDDING_DIMENSION

    def build_response(vectors):
        response = MagicMock()
        response.data = [MagicMock(index=index, embedding=vector) for index, vector in enumerate(vectors)]
        response.usage = MagicMock(prompt_tokens=len(vectors), total_tokens=len(vectors), completion_tokens=0)
        return response

    with patch("rag_core.rag.embeddings.create_embeddings", new_callable=AsyncMock) as mock_create:
        async def fake_create_embeddings(*args, input=None, **kwargs):
            if input == ["a", "b"]:
                return build_response([expected_vector_a, expected_vector_b])
            if input == ["c"]:
                return build_response([expected_vector_c])
            raise AssertionError(f"Unexpected embed input: {input}")

        mock_create.side_effect = fake_create_embeddings

        from rag_core.rag.embeddings import embed_texts

        output1 = embed_texts(["a", "b"])
        assert output1 == [expected_vector_a, expected_vector_b]

        mock_create.reset_mock()
        output2 = embed_texts(["a", "c", "b"])
        assert output2 == [expected_vector_a, expected_vector_c, expected_vector_b]
        assert mock_create.await_count == 1
        assert mock_create.call_args.kwargs["model"] == "text-embedding-3-small"
        assert mock_create.call_args.kwargs["input"] == ["c"]


def test_retrieval_result_cache_expires_after_ttl(monkeypatch) -> None:
    cache = RetrievalResultCache(ttl_seconds=1)
    embedding = [0.1] * EMBEDDING_DIMENSION
    chunk_keys = [(uuid.uuid4(), 0)]

    cache.set(embedding, 3, chunk_keys)
    assert cache.get(embedding, 3) == chunk_keys

    original_time = time.time
    monkeypatch.setattr("rag_core.core.cache.time.time", lambda: original_time() + 2)
    assert cache.get(embedding, 3) is None


def test_retrieve_chunks_reuses_retrieval_cache() -> None:
    from rag_core.rag.embeddings import EmbeddingResult
    from rag_core.rag.retrieval import retrieve_chunks

    query_embedding_cache.clear()
    retrieval_result_cache.clear()

    query_embedding = [0.1] * EMBEDDING_DIMENSION
    chunk = RetrievedChunk(
        content="cached chunk",
        document_id=uuid.uuid4(),
        filename="doc.pdf",
        chunk_index=0,
        page_number=1,
        score=0.9,
        embedding=query_embedding,
    )

    response = EmbeddingResult(
        embeddings=[query_embedding],
        usage=TokenUsage(prompt_tokens=1, model="text-embedding-3-small", is_embedding=True),
    )

    with patch("rag_core.rag.retrieval.embed_texts_with_usage", return_value=response) as mock_embed, patch(
        "rag_core.rag.retrieval._retrieve_with_session",
        return_value=[chunk],
    ) as mock_retrieve, patch(
        "rag_core.rag.retrieval._rehydrate_cached_chunks",
        return_value=[chunk],
    ) as mock_rehydrate, patch("rag_core.rag.retrieval.get_session") as mock_get_session:
        db = MagicMock()
        cm = MagicMock(__enter__=MagicMock(return_value=db), __exit__=MagicMock(return_value=None))
        mock_get_session.return_value = cm

        first_chunks, _, _ = retrieve_chunks("hello", k=2)
        assert first_chunks == [chunk]
        mock_retrieve.assert_called_once()

        mock_retrieve.reset_mock()
        second_chunks, _, _ = retrieve_chunks("hello", k=2)
        assert second_chunks == [chunk]
        mock_retrieve.assert_not_called()
        mock_rehydrate.assert_called_once()


def test_embed_cache_hit_reports_zero_usage() -> None:
    query_embedding_cache.clear()
    expected_vector = [0.5] * EMBEDDING_DIMENSION

    response = MagicMock()
    response.data = [MagicMock(index=0, embedding=expected_vector)]
    response.usage = MagicMock(prompt_tokens=5, total_tokens=5, completion_tokens=0)

    with patch("rag_core.rag.embeddings.create_embeddings", new_callable=AsyncMock) as mock_create:
        mock_create.return_value = response
        from rag_core.rag.embeddings import embed_texts_with_usage

        first = embed_texts_with_usage(["cached query"])
        second = embed_texts_with_usage(["cached query"])

    assert first.usage.prompt_tokens == 5
    assert second.usage.prompt_tokens == 0
    assert mock_create.await_count == 1


def test_query_embedding_cache_evicts_oldest_entry_at_capacity() -> None:
    cache = QueryEmbeddingCache(max_entries=2)
    vector_a = [1.0] * EMBEDDING_DIMENSION
    vector_b = [2.0] * EMBEDDING_DIMENSION
    vector_c = [3.0] * EMBEDDING_DIMENSION

    cache.set("first", vector_a)
    cache.set("second", vector_b)
    cache.set("third", vector_c)

    assert cache.get("first") is None
    assert cache.get("second") == vector_b
    assert cache.get("third") == vector_c


def test_retrieve_chunks_falls_back_when_cached_chunks_are_stale() -> None:
    from rag_core.rag.retrieval import retrieve_chunks

    query_embedding_cache.clear()
    retrieval_result_cache.clear()

    query_embedding = [0.1] * EMBEDDING_DIMENSION
    fresh_chunk = RetrievedChunk(
        content="fresh chunk",
        document_id=uuid.uuid4(),
        filename="doc.pdf",
        chunk_index=0,
        page_number=1,
        score=0.9,
        embedding=query_embedding,
    )

    response = EmbeddingResult(
        embeddings=[query_embedding],
        usage=TokenUsage(prompt_tokens=1, model="text-embedding-3-small", is_embedding=True),
    )

    with patch("rag_core.rag.retrieval.embed_texts_with_usage", return_value=response), patch(
        "rag_core.rag.retrieval._retrieve_with_session",
        return_value=[fresh_chunk],
    ) as mock_retrieve, patch(
        "rag_core.rag.retrieval._rehydrate_cached_chunks",
        side_effect=[None, [fresh_chunk]],
    ) as mock_rehydrate, patch("rag_core.rag.retrieval.get_session") as mock_get_session:
        db = MagicMock()
        cm = MagicMock(__enter__=MagicMock(return_value=db), __exit__=MagicMock(return_value=None))
        mock_get_session.return_value = cm

        first_chunks, _, _ = retrieve_chunks("hello", k=2)
        assert first_chunks == [fresh_chunk]
        mock_retrieve.assert_called_once()
        mock_rehydrate.assert_not_called()

        mock_retrieve.reset_mock()
        second_chunks, _, _ = retrieve_chunks("hello", k=2)
        assert second_chunks == [fresh_chunk]
        mock_retrieve.assert_called_once()
        mock_rehydrate.assert_called_once()


def test_document_service_clears_retrieval_cache_on_ready_state() -> None:
    from rag_core.services.document_service import update_document_status

    mock_doc = MagicMock()
    mock_doc.status = "processing"
    mock_db = MagicMock()
    mock_db.get.return_value = mock_doc

    with patch("rag_core.services.document_service.retrieval_result_cache.clear") as mock_clear:
        update_document_status(mock_db, uuid.uuid4(), "ready")

    mock_clear.assert_called_once()


def test_document_service_clears_retrieval_cache_on_delete() -> None:
    from rag_core.services.document_service import delete_document

    mock_doc = MagicMock()
    mock_db = MagicMock()
    mock_db.get.return_value = mock_doc

    with patch("rag_core.services.document_service.retrieval_result_cache.clear") as mock_clear:
        result = delete_document(mock_db, uuid.uuid4())

    assert result is True
    mock_clear.assert_called_once()
