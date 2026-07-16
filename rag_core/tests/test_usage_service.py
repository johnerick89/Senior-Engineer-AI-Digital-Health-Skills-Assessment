"""Expanded tests for usage_service persistence helpers."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from rag_core.models.usage_event import UsageKind
from rag_core.services.usage_service import (
    TokenUsage,
    apportion_integers,
    apply_usage_to_chunk,
    apply_usage_to_message,
    estimate_embed_tokens_from_texts,
    record_usage_event,
    summarize_app_usage,
    summarize_thread_usage,
)


def test_apportion_integers_sums_to_total() -> None:
    parts = apportion_integers(10, [1, 1, 1])
    assert sum(parts) == 10
    assert len(parts) == 3


def test_apportion_empty() -> None:
    assert apportion_integers(5, []) == []


def test_token_usage_cost_for_mini() -> None:
    usage = TokenUsage(
        prompt_tokens=1_000_000,
        completion_tokens=0,
        model="gpt-4o-mini",
        is_embedding=False,
    )
    assert usage.estimated_cost_usd == Decimal("0.15")


def test_estimate_embed_tokens_from_texts() -> None:
    assert estimate_embed_tokens_from_texts(["abcd"]) >= 1


def test_record_usage_event_accepts_enum_kind() -> None:
    db = MagicMock()
    usage = TokenUsage(
        prompt_tokens=3,
        completion_tokens=1,
        model="gpt-4o-mini",
        is_embedding=False,
    )
    event = record_usage_event(
        db,
        kind=UsageKind.SUGGESTION,
        usage=usage,
        thread_id=uuid.uuid4(),
    )
    assert event.kind == UsageKind.SUGGESTION.value
    assert event.prompt_tokens == 3
    db.add.assert_called_once()
    db.flush.assert_called_once()


def test_record_usage_event_accepts_string_kind() -> None:
    db = MagicMock()
    usage = TokenUsage(prompt_tokens=1, is_embedding=True, model="text-embedding-3-small")
    event = record_usage_event(db, kind="ingest_embedding", usage=usage)
    assert event.kind == "ingest_embedding"


def test_apply_usage_to_message_and_chunk() -> None:
    message = MagicMock()
    usage = TokenUsage(
        prompt_tokens=10,
        completion_tokens=5,
        model="gpt-4o-mini",
        is_embedding=False,
    )
    apply_usage_to_message(message, usage)
    assert message.prompt_tokens == 10
    assert message.completion_tokens == 5
    assert message.total_tokens == 15
    assert message.model == "gpt-4o-mini"

    chunk = MagicMock()
    apply_usage_to_chunk(
        chunk,
        prompt_tokens=8,
        cost=Decimal("0.0001"),
        model="text-embedding-3-small",
    )
    assert chunk.prompt_tokens == 8
    assert chunk.estimated_cost_usd == Decimal("0.0001")
    assert chunk.model == "text-embedding-3-small"


def test_summarize_thread_usage() -> None:
    db = MagicMock()
    db.execute.return_value.one.return_value = (4, 6, 10, Decimal("0.02"))
    summary = summarize_thread_usage(db, uuid.uuid4())
    assert summary.prompt_tokens == 4
    assert summary.completion_tokens == 6
    assert summary.total_tokens == 10
    assert summary.estimated_cost_usd == 0.02


def test_summarize_app_usage_rolls_buckets() -> None:
    db = MagicMock()
    db.execute.return_value.one.side_effect = [
        (1, 2, 3, 0.1),
        (4, 0, 4, 0.2),
        (5, 0, 5, 0.3),
    ]
    summary = summarize_app_usage(db)
    assert summary.chats.total_tokens == 3
    assert summary.suggestions.prompt_tokens == 4
    assert summary.embeddings.total_tokens == 5
    assert summary.total_tokens == 12
    assert summary.estimated_cost_usd == pytest.approx(0.6)
