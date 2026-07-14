"""Lightweight similarity-threshold + MMR reranking (no cross-encoder)."""

from __future__ import annotations

import math

from rag_core.core.logging import get_logger
from rag_core.rag.schemas import RetrievedChunk

logger = get_logger(__name__)

SIMILARITY_THRESHOLD = 0.25
RERANK_TOP_N = 4
MMR_LAMBDA = 0.7


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0
    for x, y in zip(a, b, strict=True):
        dot += x * y
        norm_a += x * x
        norm_b += y * y
    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0
    return dot / (math.sqrt(norm_a) * math.sqrt(norm_b))


def rerank_chunks(
    query_embedding: list[float],
    chunks: list[RetrievedChunk],
    *,
    threshold: float = SIMILARITY_THRESHOLD,
    top_n: int = RERANK_TOP_N,
    mmr_lambda: float = MMR_LAMBDA,
) -> list[RetrievedChunk]:
    """Filter by similarity floor, then apply MMR for diversity."""
    if not chunks or top_n <= 0:
        return []

    eligible = [c for c in chunks if c.score >= threshold]
    if not eligible:
        logger.info("rerank_all_below_threshold", threshold=threshold, input=len(chunks))
        return []

    with_vectors = [c for c in eligible if c.embedding]
    pool = with_vectors if with_vectors else eligible

    if not with_vectors or not query_embedding:
        selected = sorted(pool, key=lambda c: c.score, reverse=True)[:top_n]
        logger.info("rerank_score_only", selected=len(selected))
        return selected

    selected: list[RetrievedChunk] = []
    remaining = list(pool)

    while remaining and len(selected) < top_n:
        best: RetrievedChunk | None = None
        best_mmr = float("-inf")
        for candidate in remaining:
            relevance = _cosine_similarity(query_embedding, candidate.embedding)
            if selected:
                redundancy = max(
                    _cosine_similarity(candidate.embedding, s.embedding) for s in selected
                )
            else:
                redundancy = 0.0
            mmr_score = mmr_lambda * relevance - (1.0 - mmr_lambda) * redundancy
            if mmr_score > best_mmr:
                best_mmr = mmr_score
                best = candidate
        if best is None:
            break
        selected.append(best)
        remaining.remove(best)

    logger.info("rerank_mmr_complete", selected=len(selected), pool=len(pool))
    return selected
