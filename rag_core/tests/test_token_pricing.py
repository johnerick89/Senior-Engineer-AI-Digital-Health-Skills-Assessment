"""Tests for rag_core.core.token_pricing."""

import pytest

from rag_core.core.token_pricing import (
    estimate_cost_usd_for_rows,
    estimate_step_cost_usd,
)


def test_estimate_chat_cost_for_known_model() -> None:
    # gpt-4o-mini: $0.15 / 1M prompt, $0.60 / 1M completion
    cost = estimate_step_cost_usd(
        model="gpt-4o-mini",
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        is_embedding=False,
    )
    assert cost == pytest.approx(0.75)


def test_estimate_embedding_cost_for_known_model() -> None:
    # text-embedding-3-small: $0.02 / 1M input tokens
    cost = estimate_step_cost_usd(
        model="text-embedding-3-small",
        prompt_tokens=1_000_000,
        completion_tokens=0,
        is_embedding=True,
    )
    assert cost == pytest.approx(0.02)


def test_estimate_embedding_ignores_completion_tokens() -> None:
    cost = estimate_step_cost_usd(
        model="text-embedding-3-small",
        prompt_tokens=500_000,
        completion_tokens=999_999,
        is_embedding=True,
    )
    assert cost == pytest.approx(0.01)


def test_unknown_chat_model_falls_back_to_gpt_4o_mini_rates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING"):
        cost = estimate_step_cost_usd(
            model="definitely-not-a-real-model",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            is_embedding=False,
        )
    assert cost == pytest.approx(0.75)
    assert "Unknown chat model" in caplog.text


def test_unknown_embed_model_falls_back_to_small_rates(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level("WARNING"):
        cost = estimate_step_cost_usd(
            model="mystery-embed",
            prompt_tokens=1_000_000,
            completion_tokens=0,
            is_embedding=True,
        )
    assert cost == pytest.approx(0.02)
    assert "Unknown embedding model" in caplog.text


def test_estimate_cost_usd_for_rows_sums_steps() -> None:
    total = estimate_cost_usd_for_rows(
        [
            ("embed", 1_000_000, 0, "text-embedding-3-small", True),
            ("generate", 1_000_000, 1_000_000, "gpt-4o-mini", False),
        ]
    )
    assert total == pytest.approx(0.77)


def test_estimate_cost_usd_for_rows_empty() -> None:
    assert estimate_cost_usd_for_rows([]) == 0.0
