"""Tests for usage_service helpers."""

from decimal import Decimal

from rag_core.services.usage_service import (
    TokenUsage,
    apportion_integers,
    estimate_embed_tokens_from_texts,
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
