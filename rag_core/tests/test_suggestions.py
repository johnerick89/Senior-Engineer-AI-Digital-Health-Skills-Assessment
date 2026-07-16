"""Tests for document-grounded chat topic suggestions."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag_core.rag.suggestions import (
    _fallback_topics,
    _parse_topics,
    suggest_chat_topics,
)
from rag_core.services.document_service import DocumentSnippet


def test_parse_topics_from_json_array() -> None:
    raw = '["What is ACT for malaria?", "Summarize CHW outreach duties."]'
    assert _parse_topics(raw, limit=5) == [
        "What is ACT for malaria?",
        "Summarize CHW outreach duties.",
    ]


def test_parse_topics_dedupes_and_caps() -> None:
    raw = (
        '["First unique question here", "first unique question here", '
        '"Second unique question here", "Third unique question here", '
        '"Fourth unique question here", "Fifth unique question here", '
        '"Sixth unique question here"]'
    )
    topics = _parse_topics(raw, limit=5)
    assert topics == [
        "First unique question here",
        "Second unique question here",
        "Third unique question here",
        "Fourth unique question here",
        "Fifth unique question here",
    ]


def test_fallback_topics_from_snippets() -> None:
    snippets = [
        DocumentSnippet(
            filename="malaria.pdf",
            content="ACT is the primary treatment for uncomplicated malaria cases.",
            page_number=1,
        ),
        DocumentSnippet(
            filename="chw.pdf",
            content="CHWs deliver childhood immunizations at outreach posts.",
            page_number=2,
        ),
    ]
    topics = _fallback_topics(snippets, limit=5)
    assert len(topics) == 2
    assert "malaria" in topics[0].lower() or "ACT" in topics[0]


@pytest.mark.asyncio
async def test_suggest_chat_topics_uses_llm() -> None:
    snippet = DocumentSnippet(
        filename="guide.pdf",
        content="Community health workers support immunization outreach.",
        page_number=1,
    )
    response = MagicMock()
    response.choices = [
        MagicMock(
            message=MagicMock(
                content='["What immunization support do CHWs provide?"]'
            )
        )
    ]

    with (
        patch("rag_core.rag.suggestions.get_session") as mock_session,
        patch(
            "rag_core.rag.suggestions.sample_ready_document_snippets",
            return_value=[snippet],
        ),
        patch(
            "rag_core.rag.suggestions.create_chat_completion",
            new_callable=AsyncMock,
            return_value=response,
        ),
    ):
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        cm.__exit__.return_value = None
        mock_session.return_value = cm
        topics = await suggest_chat_topics(limit=5)

    assert topics == ["What immunization support do CHWs provide?"]


@pytest.mark.asyncio
async def test_suggest_chat_topics_empty_without_docs() -> None:
    with (
        patch("rag_core.rag.suggestions.get_session") as mock_session,
        patch(
            "rag_core.rag.suggestions.sample_ready_document_snippets",
            return_value=[],
        ),
    ):
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        cm.__exit__.return_value = None
        mock_session.return_value = cm
        assert await suggest_chat_topics() == []


@pytest.mark.asyncio
async def test_suggest_chat_topics_cap_zero() -> None:
    assert await suggest_chat_topics(limit=0) == []


@pytest.mark.asyncio
async def test_suggest_chat_topics_falls_back_on_llm_error() -> None:
    snippet = DocumentSnippet(
        filename="guide.pdf",
        content="Community health workers support immunization outreach.",
        page_number=1,
    )
    with (
        patch("rag_core.rag.suggestions.get_session") as mock_session,
        patch(
            "rag_core.rag.suggestions.sample_ready_document_snippets",
            return_value=[snippet],
        ),
        patch(
            "rag_core.rag.suggestions.create_chat_completion",
            new_callable=AsyncMock,
            side_effect=RuntimeError("llm down"),
        ),
    ):
        cm = MagicMock()
        cm.__enter__.return_value = MagicMock()
        cm.__exit__.return_value = None
        mock_session.return_value = cm
        topics = await suggest_chat_topics(limit=3)
    assert len(topics) >= 1


def test_format_snippet_block_includes_page() -> None:
    from rag_core.rag.suggestions import _format_snippet_block

    block = _format_snippet_block(
        [
            DocumentSnippet(filename="a.pdf", content="hello", page_number=3),
            DocumentSnippet(filename="b.pdf", content="world", page_number=None),
        ]
    )
    assert "page 3" in block
    assert "a.pdf" in block
    assert "b.pdf" in block
