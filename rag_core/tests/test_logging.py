"""Tests for rag_core.core.logging."""

from unittest.mock import MagicMock, patch

import pytest

from rag_core.core import logging as rag_logging
from rag_core.core.logging import configure_logging, get_logger


def test_get_logger_returns_usable_logger() -> None:
    configure_logging()
    logger = get_logger("rag_core.tests")
    assert hasattr(logger, "info")
    assert hasattr(logger, "bind")


@patch("rag_core.core.logging.structlog.configure")
def test_configure_logging_uses_console_renderer_outside_production(
    mock_configure: MagicMock,
) -> None:
    mock_settings = MagicMock(app_env="development", log_level="INFO")
    with patch.object(rag_logging, "settings", mock_settings):
        configure_logging()

    processors = mock_configure.call_args.kwargs["processors"]
    assert any(type(p).__name__ == "ConsoleRenderer" for p in processors)
    assert not any(type(p).__name__ == "JSONRenderer" for p in processors)


@patch("rag_core.core.logging.structlog.configure")
def test_configure_logging_uses_json_renderer_in_production(
    mock_configure: MagicMock,
) -> None:
    mock_settings = MagicMock(app_env="production", log_level="WARNING")
    with patch.object(rag_logging, "settings", mock_settings):
        configure_logging()

    processors = mock_configure.call_args.kwargs["processors"]
    assert any(type(p).__name__ == "JSONRenderer" for p in processors)
    assert not any(type(p).__name__ == "ConsoleRenderer" for p in processors)


@patch("rag_core.core.logging.structlog.configure")
def test_configure_logging_includes_shared_processors(
    mock_configure: MagicMock,
) -> None:
    mock_settings = MagicMock(app_env="development", log_level="INFO")
    with patch.object(rag_logging, "settings", mock_settings):
        configure_logging()

    processors = mock_configure.call_args.kwargs["processors"]
    processor_names = {type(p).__name__ for p in processors}
    assert "TimeStamper" in processor_names
    assert len(processors) >= 4


@pytest.mark.asyncio
async def test_stream_rag_answer_logs_retrieval_metadata() -> None:
    from rag_core.rag.generation import stream_rag_answer
    from rag_core.rag.schemas import ChatQuery, RetrievedChunk

    chunk = RetrievedChunk(
        content="chunk text",
        document_id=__import__("uuid").uuid4(),
        filename="doc.pdf",
        chunk_index=0,
        page_number=1,
        score=0.91,
        embedding=[1.0, 0.0, 0.0],
    )

    async def fake_stream(*args, **kwargs):
        yield "answer"

    with patch(
        "rag_core.rag.generation.retrieve_chunks_async",
        return_value=([chunk], [1.0, 0.0, 0.0], None),
    ), patch(
        "rag_core.rag.generation.rerank_chunks",
        return_value=[chunk],
    ), patch(
        "rag_core.rag.generation.stream_chat_tokens",
        side_effect=fake_stream,
    ), patch("rag_core.rag.generation.logger") as mock_logger:
        output = [part async for part in stream_rag_answer(ChatQuery(input="question"))]

    assert output == ["answer"]
    mock_logger.info.assert_any_call(
        "rag.retrieval.completed",
        retrieved_chunk_count=1,
        selected_chunk_count=1,
        chunks=[
            {
                "filename": "doc.pdf",
                "chunk_index": 0,
                "score": 0.91,
            }
        ],
    )
