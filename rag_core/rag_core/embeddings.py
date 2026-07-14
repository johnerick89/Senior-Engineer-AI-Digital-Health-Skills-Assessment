"""Embedding model configuration and OpenAI embedding helpers."""

from __future__ import annotations

import asyncio

from rag_core.core.config import get_settings
from rag_core.core.openai_client import get_async_client

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSION = 1536

# OpenAI allows large batches; keep a hard ceiling independent of ingest settings.
_MAX_EMBED_BATCH_SIZE = 256


async def _embed_texts_async(texts: list[str]) -> list[list[float]]:
    if not texts:
        return []

    client = get_async_client()
    batch_size = min(get_settings().ingestion_batch_size, _MAX_EMBED_BATCH_SIZE)
    embeddings: list[list[float]] = []

    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        response = await client.embeddings.create(model=EMBEDDING_MODEL, input=batch)
        ordered = sorted(response.data, key=lambda item: item.index)
        for item in ordered:
            vector = list(item.embedding)
            if len(vector) != EMBEDDING_DIMENSION:
                raise ValueError(
                    f"Expected embedding dimension {EMBEDDING_DIMENSION}, got {len(vector)}"
                )
            embeddings.append(vector)

    return embeddings


def embed_texts(texts: list[str]) -> list[list[float]]:
    """Embed texts with the pinned model. Sync wrapper over AsyncOpenAI."""
    return asyncio.run(_embed_texts_async(texts))
