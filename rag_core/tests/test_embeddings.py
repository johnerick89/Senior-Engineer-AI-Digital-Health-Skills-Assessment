"""Tests for rag_core.rag.embeddings.embed_texts."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag_core.rag.embeddings import EMBEDDING_DIMENSION, EMBEDDING_MODEL, embed_texts


def test_embedding_model_is_pinned() -> None:
    assert EMBEDDING_MODEL == "text-embedding-3-small"


def test_embedding_dimension_matches_openai_small_model() -> None:
    assert EMBEDDING_DIMENSION == 1536


def _fake_embedding(index: int, dim: int = EMBEDDING_DIMENSION) -> MagicMock:
    item = MagicMock()
    item.index = index
    item.embedding = [float(index)] * dim
    return item


@patch("rag_core.rag.embeddings.create_embeddings")
def test_embed_texts_empty_list(mock_create: MagicMock) -> None:
    assert embed_texts([]) == []
    mock_create.assert_not_called()


@patch("rag_core.rag.embeddings.get_settings")
@patch("rag_core.rag.embeddings.create_embeddings", new_callable=AsyncMock)
def test_embed_texts_batches_and_returns_vectors(
    mock_create: AsyncMock,
    mock_get_settings: MagicMock,
) -> None:
    mock_get_settings.return_value = MagicMock(ingestion_batch_size=2)
    response = MagicMock()
    response.data = [_fake_embedding(1), _fake_embedding(0)]
    response.usage = MagicMock(prompt_tokens=4, total_tokens=4, completion_tokens=0)
    mock_create.return_value = response

    vectors = embed_texts(["a", "b"])

    mock_create.assert_awaited_once_with(model=EMBEDDING_MODEL, input=["a", "b"])
    assert len(vectors) == 2
    assert vectors[0][0] == 0.0
    assert vectors[1][0] == 1.0
    assert all(len(v) == EMBEDDING_DIMENSION for v in vectors)


@patch("rag_core.rag.embeddings.get_settings")
@patch("rag_core.rag.embeddings.create_embeddings", new_callable=AsyncMock)
def test_embed_texts_rejects_wrong_dimension(
    mock_create: AsyncMock,
    mock_get_settings: MagicMock,
) -> None:
    mock_get_settings.return_value = MagicMock(ingestion_batch_size=100)
    response = MagicMock()
    response.data = [_fake_embedding(0, dim=8)]
    response.usage = MagicMock(prompt_tokens=1, total_tokens=1, completion_tokens=0)
    mock_create.return_value = response

    with pytest.raises(ValueError, match="Expected embedding dimension"):
        embed_texts(["bad"])
