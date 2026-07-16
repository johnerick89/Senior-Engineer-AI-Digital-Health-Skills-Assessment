"""Embedding model configuration and helpers (via centralized LLM client)."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import cast

from rag_core.core.cache import normalize_query, query_embedding_cache
from rag_core.core.config import get_settings
from rag_core.core.embedding_defaults import EMBEDDING_DIMENSION, EMBEDDING_MODEL
from rag_core.core.openai_client import create_embeddings
from rag_core.core.token_usage import (
    TokenUsage,
    estimate_embed_tokens_from_texts,
    usage_from_openai_response,
)

__all__ = [
    "EMBEDDING_DIMENSION",
    "EMBEDDING_MODEL",
    "EmbeddingResult",
    "embed_texts",
    "embed_texts_with_usage",
]

# OpenAI allows large batches; keep a hard ceiling independent of ingest settings.
_MAX_EMBED_BATCH_SIZE = 256


@dataclass(frozen=True)
class EmbeddingResult:
    """Vectors plus aggregate usage for the embed call(s)."""

    embeddings: list[list[float]]
    usage: TokenUsage


async def _embed_texts_async(texts: list[str]) -> EmbeddingResult:
    if not texts:
        return EmbeddingResult(
            embeddings=[],
            usage=TokenUsage(model=EMBEDDING_MODEL, is_embedding=True),
        )

    batch_size = min(get_settings().ingestion_batch_size, _MAX_EMBED_BATCH_SIZE)
    embeddings: list[list[float]] = [None] * len(texts)  # type: ignore[assignment]
    missed_texts: list[str] = []
    miss_positions: dict[str, list[int]] = {}

    for index, text in enumerate(texts):
        key = normalize_query(text)
        cached = query_embedding_cache.get(key)
        if cached is not None:
            embeddings[index] = cached
            continue

        if key not in miss_positions:
            missed_texts.append(text)
            miss_positions[key] = []
        miss_positions[key].append(index)

    prompt_tokens = 0
    if missed_texts:
        response = await create_embeddings(model=EMBEDDING_MODEL, input=missed_texts)
        batch_usage = usage_from_openai_response(
            response,
            model=EMBEDDING_MODEL,
            is_embedding=True,
        )
        if batch_usage.prompt_tokens <= 0:
            prompt_tokens += estimate_embed_tokens_from_texts(missed_texts)
        else:
            prompt_tokens += batch_usage.prompt_tokens

        ordered = sorted(response.data, key=lambda item: item.index)
        for item in ordered:
            vector = list(item.embedding)
            if len(vector) != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Expected embedding dimension {EMBEDDING_DIMENSION}, got {len(vector)}"
                )
            normalized_key = normalize_query(missed_texts[item.index])
            query_embedding_cache.set(normalized_key, vector)
            for position in miss_positions[normalized_key]:
                embeddings[position] = vector

    result_embeddings = [cast(list[float], e) for e in embeddings]

    return EmbeddingResult(
        embeddings=result_embeddings,
        usage=TokenUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=0,
            model=EMBEDDING_MODEL,
            is_embedding=True,
        ),
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the pinned model (OpenAI, with OpenRouter fallback)."""
    return embed_texts_with_usage(texts).embeddings


def embed_texts_with_usage(texts: list[str]) -> EmbeddingResult:
    """Embed texts and return vectors plus usage metadata."""
    return asyncio.run(_embed_texts_async(texts))


async def embed_texts_with_usage_async(texts: list[str]) -> EmbeddingResult:
    """Async variant of ``embed_texts_with_usage``."""
    return await _embed_texts_async(texts)
