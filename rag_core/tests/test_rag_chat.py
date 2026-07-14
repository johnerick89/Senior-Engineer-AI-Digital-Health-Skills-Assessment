"""Unit tests for chat RAG schemas, retrieval, rerank, and generation."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from rag_core.rag.generation import (
    EMPTY_CORPUS_MESSAGE,
    build_rag_messages,
    format_context_blocks,
    format_no_match_answer,
    stream_chat_tokens,
    stream_rag_answer,
)
from rag_core.rag.reranking import SIMILARITY_THRESHOLD, rerank_chunks
from rag_core.rag.retrieval import _retrieve_with_session, retrieve_chunks
from rag_core.rag.schemas import ChatQuery, ChatTurn, RetrievedChunk


def _chunk(
    *,
    content: str = "chunk text",
    score: float = 0.9,
    embedding: list[float] | None = None,
    filename: str = "doc.pdf",
) -> RetrievedChunk:
    return RetrievedChunk(
        content=content,
        document_id=uuid.uuid4(),
        filename=filename,
        chunk_index=0,
        page_number=1,
        score=score,
        embedding=embedding if embedding is not None else [1.0, 0.0, 0.0],
    )


def test_chat_query_rejects_blank_input() -> None:
    with pytest.raises(ValidationError):
        ChatQuery(input="   ")


def test_chat_turn_rejects_blank_response() -> None:
    with pytest.raises(ValidationError):
        ChatTurn(input="hi", response="  ")


def test_chat_query_history_max_length() -> None:
    turns = [ChatTurn(input=f"q{i}", response=f"a{i}") for i in range(21)]
    with pytest.raises(ValidationError):
        ChatQuery(input="hello", history=turns)


def test_retrieve_with_session_maps_rows() -> None:
    doc_id = uuid.uuid4()
    chunk = MagicMock()
    chunk.content = "hello community health"
    chunk.document_id = doc_id
    chunk.chunk_index = 2
    chunk.page_number = 3
    chunk.embedding = [0.1, 0.2, 0.3]

    db = MagicMock()
    db.execute.return_value.all.return_value = [
        (chunk, "guide.pdf", 0.2),
    ]

    results = _retrieve_with_session(db, [0.0, 1.0, 0.0], k=5)
    assert len(results) == 1
    assert results[0].content == "hello community health"
    assert results[0].filename == "guide.pdf"
    assert results[0].score == pytest.approx(0.8)
    assert results[0].embedding == [0.1, 0.2, 0.3]
    db.execute.assert_called_once()


@patch("rag_core.rag.retrieval.get_session")
@patch("rag_core.rag.retrieval.embed_texts_with_usage")
def test_retrieve_chunks_embeds_and_queries(
    mock_embed: MagicMock,
    mock_get_session: MagicMock,
) -> None:
    from rag_core.rag.embeddings import EmbeddingResult
    from rag_core.services.usage_service import TokenUsage

    mock_embed.return_value = EmbeddingResult(
        embeddings=[[0.5, 0.5]],
        usage=TokenUsage(prompt_tokens=2, model="text-embedding-3-small", is_embedding=True),
    )
    db = MagicMock()
    db.execute.return_value.all.return_value = []
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None
    mock_get_session.return_value = cm

    chunks, embedding, _usage = retrieve_chunks("malaria protocol", k=3)
    assert chunks == []
    assert embedding == [0.5, 0.5]
    mock_embed.assert_called_once_with(["malaria protocol"])


def test_rerank_drops_below_threshold() -> None:
    low = _chunk(score=SIMILARITY_THRESHOLD - 0.05, content="irrelevant")
    assert rerank_chunks([1.0, 0.0, 0.0], [low]) == []


def test_rerank_mmr_prefers_diverse_chunks() -> None:
    query = [1.0, 0.0, 0.0]
    # Near-duplicate pair vs an orthogonal chunk; lower lambda so diversity wins.
    a = _chunk(content="a", score=0.95, embedding=[1.0, 0.0, 0.0])
    b = _chunk(content="b", score=0.94, embedding=[0.999, 0.001, 0.0])
    c = _chunk(content="c", score=0.7, embedding=[0.0, 1.0, 0.0])

    selected = rerank_chunks(
        query,
        [a, b, c],
        top_n=2,
        threshold=0.2,
        mmr_lambda=0.4,
    )
    texts = {chunk.content for chunk in selected}
    assert "a" in texts
    # Second pick should favor diversity over near-duplicate b.
    assert "c" in texts


def test_build_rag_messages_includes_history_and_context() -> None:
    chunk = _chunk(content="CHWs deliver vaccines.", filename="chw.pdf")
    messages = build_rag_messages(
        user_input="What do CHWs do?",
        history=[ChatTurn(input="hi", response="hello")],
        chunks=[chunk],
    )
    assert messages[0]["role"] == "system"
    assert "document context" in messages[0]["content"].lower()
    assert messages[1] == {"role": "user", "content": "hi"}
    assert messages[2] == {"role": "assistant", "content": "hello"}
    assert messages[-1]["role"] == "user"
    assert "CHWs deliver vaccines." in messages[-1]["content"]
    assert "chw.pdf" in messages[-1]["content"]
    assert "What do CHWs do?" in messages[-1]["content"]


def test_format_context_blocks_empty() -> None:
    assert format_context_blocks([]) == "(no context)"


def test_format_no_match_answer() -> None:
    assert format_no_match_answer([]) == EMPTY_CORPUS_MESSAGE
    text = format_no_match_answer(["chw.pdf", "joshua.pdf"])
    assert "couldn't find that" in text.lower()
    assert "chw.pdf" in text
    assert "joshua.pdf" in text


@pytest.mark.asyncio
async def test_stream_chat_tokens_yields_deltas() -> None:
    class Delta:
        def __init__(self, content: str | None) -> None:
            self.content = content

    class Choice:
        def __init__(self, content: str | None) -> None:
            self.delta = Delta(content)

    class Event:
        def __init__(self, content: str | None) -> None:
            self.choices = [Choice(content)]

    async def fake_stream():
        yield Event("Hel")
        yield Event("lo")
        yield Event(None)

    with patch(
        "rag_core.rag.generation.create_chat_completion",
        new_callable=AsyncMock,
        return_value=fake_stream(),
    ):
        parts = [p async for p in stream_chat_tokens([{"role": "user", "content": "hi"}])]
    assert "".join(parts) == "Hello"


@pytest.mark.asyncio
async def test_stream_rag_answer_empty_corpus_lists_fallback() -> None:
    with (
        patch(
            "rag_core.rag.generation.retrieve_chunks_async",
            new_callable=AsyncMock,
            return_value=([], [], None),
        ),
        patch(
            "rag_core.rag.generation.list_available_documents",
            return_value=[],
        ),
    ):
        text = "".join(
            [p async for p in stream_rag_answer(ChatQuery(input="Where do CHWs work?"))]
        )
    assert text == EMPTY_CORPUS_MESSAGE


@pytest.mark.asyncio
async def test_stream_rag_answer_no_match_lists_documents() -> None:
    chunk = _chunk(score=0.01)
    with (
        patch(
            "rag_core.rag.generation.retrieve_chunks_async",
            new_callable=AsyncMock,
            return_value=([chunk], [1.0, 0.0, 0.0], None),
        ),
        patch(
            "rag_core.rag.generation.rerank_chunks",
            return_value=[],
        ),
        patch(
            "rag_core.rag.generation.list_available_documents",
            return_value=["chw.pdf", "CV - Joshua Oluoch.pdf"],
        ),
    ):
        text = "".join(
            [
                p
                async for p in stream_rag_answer(
                    ChatQuery(input="what is the capital of Mars?")
                )
            ]
        )
    assert "couldn't find that" in text.lower()
    assert "CV - Joshua Oluoch.pdf" in text
    assert "chw.pdf" in text


@pytest.mark.asyncio
async def test_stream_rag_answer_does_not_short_circuit_capability_phrasing() -> None:
    """Questions like 'what can you tell me about X' must go through retrieval."""
    chunk = _chunk(score=0.9, content="Joshua is an engineer.", filename="CV - Joshua.pdf")

    async def fake_tokens(_messages, **_kwargs):
        yield "Joshua is an engineer."

    with (
        patch(
            "rag_core.rag.generation.retrieve_chunks_async",
            new_callable=AsyncMock,
            return_value=([chunk], [1.0, 0.0, 0.0], None),
        ) as mock_retrieve,
        patch(
            "rag_core.rag.generation.rerank_chunks",
            return_value=[chunk],
        ),
        patch(
            "rag_core.rag.generation.stream_chat_tokens",
            side_effect=fake_tokens,
        ),
    ):
        text = "".join(
            [
                p
                async for p in stream_rag_answer(
                    ChatQuery(input="what can you tell me about Joshua")
                )
            ]
        )
    mock_retrieve.assert_awaited_once()
    assert text == "Joshua is an engineer."


@pytest.mark.asyncio
async def test_stream_rag_answer_streams_model() -> None:
    chunk = _chunk(score=0.9, content="Vaccines at outreach posts.")

    async def fake_tokens(_messages, **_kwargs):
        yield "Based on "
        yield "the doc."

    with (
        patch(
            "rag_core.rag.generation.retrieve_chunks_async",
            new_callable=AsyncMock,
            return_value=([chunk], [1.0, 0.0, 0.0], None),
        ),
        patch(
            "rag_core.rag.generation.rerank_chunks",
            return_value=[chunk],
        ),
        patch(
            "rag_core.rag.generation.stream_chat_tokens",
            side_effect=fake_tokens,
        ),
    ):
        text = "".join([p async for p in stream_rag_answer(ChatQuery(input="vaccines?"))])
    assert text == "Based on the doc."
