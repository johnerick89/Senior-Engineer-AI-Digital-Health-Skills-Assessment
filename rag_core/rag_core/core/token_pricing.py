"""Approximate USD list prices per 1M tokens for cost estimates.

Rates are conservative defaults; override via env in `Settings` if needed.
Source order-of-magnitude: OpenAI public pricing (verify for your contract).
Last verified: 2026-01 — re-check against provider pricing periodically,
prices and model lineups change without notice.
"""

from __future__ import annotations

import logging
from typing import Final

logger = logging.getLogger(__name__)

# (USD per 1M prompt tokens, USD per 1M completion tokens)
_MODEL_CHAT_RATES: Final[dict[str, tuple[float, float]]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o-2024-08-06": (2.50, 10.00),
    "gpt-4o-mini-2024-07-18": (0.15, 0.60),
}

# Embeddings: USD per 1M input tokens (no completion component)
_MODEL_EMBED_RATES: Final[dict[str, float]] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
}

_DEFAULT_CHAT_MODEL: Final[str] = "gpt-4o-mini"
_DEFAULT_EMBED_MODEL: Final[str] = "text-embedding-3-small"


def _chat_rates(model: str) -> tuple[float, float]:
    """Look up (prompt, completion) USD/1M rates for a chat model.

    Falls back to gpt-4o-mini tier pricing for unrecognized models, logging
    a warning so a typo'd or newly released model name doesn't silently
    produce a wrong-but-plausible cost estimate.
    """
    if model in _MODEL_CHAT_RATES:
        return _MODEL_CHAT_RATES[model]
    logger.warning(
        "Unknown chat model %r for cost estimation; falling back to %r rates",
        model,
        _DEFAULT_CHAT_MODEL,
    )
    return _MODEL_CHAT_RATES[_DEFAULT_CHAT_MODEL]


def _embed_rate(model: str) -> float:
    """Look up USD/1M input-token rate for an embedding model.

    Falls back to text-embedding-3-small pricing for unrecognized models,
    logging a warning for the same reason as `_chat_rates`.
    """
    if model in _MODEL_EMBED_RATES:
        return _MODEL_EMBED_RATES[model]
    logger.warning(
        "Unknown embedding model %r for cost estimation; falling back to %r rates",
        model,
        _DEFAULT_EMBED_MODEL,
    )
    return _MODEL_EMBED_RATES[_DEFAULT_EMBED_MODEL]


def estimate_step_cost_usd(
    *,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    is_embedding: bool,
) -> float:
    """Estimate USD cost for a single embedding or chat completion call.

    `is_embedding` must be supplied by the caller based on which API was
    actually invoked (`.embeddings.create()` vs `.chat.completions.create()`)
    — it is not inferred from step naming, since naming conventions drift
    and retrieval (a pgvector query, no API call) is not the same thing as
    embedding generation (an OpenAI API call during ingestion or at
    query-time to embed the user's question).
    """
    if is_embedding:
        rate = _embed_rate(model)
        return (prompt_tokens / 1_000_000.0) * rate
    inp, out = _chat_rates(model)
    return (prompt_tokens / 1_000_000.0) * inp + (completion_tokens / 1_000_000.0) * out


def estimate_cost_usd_for_rows(
    rows: list[tuple[str, int, int, str, bool]],
) -> float:
    """Sum estimated USD cost across multiple pipeline steps.

    Each row: (step_name, prompt_tokens, completion_tokens, model, is_embedding).
    `step_name` is kept for logging/debugging context only — it does not
    drive cost-type classification, `is_embedding` does.
    """
    total = 0.0
    for step_name, prompt_tokens, completion_tokens, model, is_embedding in rows:
        total += estimate_step_cost_usd(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            is_embedding=is_embedding,
        )
    return total