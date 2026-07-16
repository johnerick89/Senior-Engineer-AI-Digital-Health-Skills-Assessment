from __future__ import annotations

import hashlib
import struct
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Iterable

from rag_core.core.embedding_defaults import EMBEDDING_DIMENSION

CACHE_MAX_QUERY_EMBEDDINGS = 512
RETRIEVAL_CACHE_TTL_SECONDS = 300


def normalize_query(text: str) -> str:
    """Normalize text for query embedding cache keys."""
    return " ".join(text.split()).strip().lower()


class QueryEmbeddingCache:
    """A small process-local cache for normalized query embeddings."""

    def __init__(self, max_entries: int = CACHE_MAX_QUERY_EMBEDDINGS) -> None:
        self._max_entries = max_entries
        self._store: OrderedDict[str, list[float]] = OrderedDict()

    def get(self, text: str) -> list[float] | None:
        key = normalize_query(text)
        if not key:
            return None
        embedding = self._store.get(key)
        if embedding is None:
            return None
        self._store.move_to_end(key)
        return embedding

    def set(self, text: str, embedding: list[float]) -> None:
        if len(embedding) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"Expected embedding dimension {EMBEDDING_DIMENSION}, got {len(embedding)}"
            )
        key = normalize_query(text)
        if not key:
            return
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = embedding
        if len(self._store) > self._max_entries:
            self._store.popitem(last=False)

    def clear(self) -> None:
        self._store.clear()


@dataclass(frozen=True)
class RetrievalResultCacheEntry:
    """One cached retrieval result with an expiry timestamp."""

    chunk_keys: list[tuple[str, int]]
    expires_at: float


class RetrievalResultCache:
    """TTL cache for retrieved chunk identifiers."""

    def __init__(self, ttl_seconds: int = RETRIEVAL_CACHE_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._store: dict[str, RetrievalResultCacheEntry] = {}

    @staticmethod
    def _hash_embedding(embedding: list[float]) -> str:
        packed = struct.pack(f">{len(embedding)}f", *embedding)
        return hashlib.sha256(packed).hexdigest()

    def _cache_key(self, embedding: list[float], k: int) -> str:
        return f"{self._hash_embedding(embedding)}:{k}"

    def get(self, embedding: list[float], k: int) -> list[tuple[str, int]] | None:
        key = self._cache_key(embedding, k)
        entry = self._store.get(key)
        if entry is None:
            return None
        if time.time() >= entry.expires_at:
            del self._store[key]
            return None
        return entry.chunk_keys

    def set(
        self,
        embedding: list[float],
        k: int,
        chunk_keys: Iterable[tuple[str, int]],
    ) -> None:
        key = self._cache_key(embedding, k)
        self._store[key] = RetrievalResultCacheEntry(
            chunk_keys=list(chunk_keys),
            expires_at=time.time() + self._ttl_seconds,
        )

    def clear(self) -> None:
        self._store.clear()


query_embedding_cache = QueryEmbeddingCache()
retrieval_result_cache = RetrievalResultCache()
