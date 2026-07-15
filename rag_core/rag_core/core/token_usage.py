"""Pure token/cost helpers with no ORM imports (safe for embeddings)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from rag_core.core.token_pricing import estimate_step_cost_usd


@dataclass(frozen=True)
class TokenUsage:
    """Normalized usage for one provider call."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    model: str = ""
    is_embedding: bool = False

    @property
    def total_tokens(self) -> int:
        return int(self.prompt_tokens) + int(self.completion_tokens)

    @property
    def estimated_cost_usd(self) -> Decimal:
        return Decimal(
            str(
                estimate_step_cost_usd(
                    model=self.model or "gpt-4o-mini",
                    prompt_tokens=self.prompt_tokens,
                    completion_tokens=self.completion_tokens,
                    is_embedding=self.is_embedding,
                )
            )
        )


def usage_from_openai_response(
    response: object,
    *,
    model: str,
    is_embedding: bool,
) -> TokenUsage:
    """Extract usage from an OpenAI-style response object when present."""
    usage = getattr(response, "usage", None)
    prompt = int(getattr(usage, "prompt_tokens", 0) or 0) if usage is not None else 0
    completion = (
        int(getattr(usage, "completion_tokens", 0) or 0) if usage is not None else 0
    )
    # Embeddings often only set total_tokens / prompt_tokens.
    if is_embedding and prompt == 0 and usage is not None:
        prompt = int(getattr(usage, "total_tokens", 0) or 0)
    return TokenUsage(
        prompt_tokens=prompt,
        completion_tokens=0 if is_embedding else completion,
        model=model,
        is_embedding=is_embedding,
    )


def estimate_embed_tokens_from_texts(texts: list[str]) -> int:
    """Rough fallback when the API omits usage (~4 chars/token)."""
    return max(1, sum(max(1, len(t) // 4) for t in texts)) if texts else 0


def apportion_integers(total: int, weights: list[int]) -> list[int]:
    """Split ``total`` across ``weights`` proportionally (largest remainder)."""
    if not weights:
        return []
    if total <= 0:
        return [0] * len(weights)
    weight_sum = sum(max(0, w) for w in weights) or len(weights)
    raw = [(max(0, w) / weight_sum) * total for w in weights]
    floors = [int(x) for x in raw]
    rem = total - sum(floors)
    order = sorted(
        range(len(weights)),
        key=lambda i: (raw[i] - floors[i], weights[i]),
        reverse=True,
    )
    for i in order[:rem]:
        floors[i] += 1
    return floors
