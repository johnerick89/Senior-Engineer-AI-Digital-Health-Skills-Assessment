"""Vector similarity search over document_chunks (pgvector cosine)."""

from __future__ import annotations

import asyncio

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from rag_core.core.cache import retrieval_result_cache
from rag_core.core.config import get_settings
from rag_core.core.logging import get_logger
from rag_core.core.token_usage import TokenUsage
from rag_core.db.session import get_session
from rag_core.models.document import Document, DocumentStatus
from rag_core.models.document_chunk import DocumentChunk
from rag_core.rag.embeddings import EMBEDDING_MODEL, embed_texts_with_usage
from rag_core.rag.schemas import RetrievedChunk

logger = get_logger(__name__)


def _retrieve_with_session(
    db: Session,
    query_embedding: list[float],
    k: int,
) -> list[RetrievedChunk]:
    distance = DocumentChunk.embedding.cosine_distance(query_embedding)
    stmt = (
        select(DocumentChunk, Document.filename, distance.label("distance"))
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(DocumentChunk.embedding.is_not(None))
        .where(Document.status == DocumentStatus.READY.value)
        .order_by(distance)
        .limit(k)
    )
    rows = db.execute(stmt).all()
    chunks: list[RetrievedChunk] = []
    for chunk, filename, dist in rows:
        score = max(0.0, 1.0 - float(dist))
        embedding = list(chunk.embedding) if chunk.embedding is not None else []
        chunks.append(
            RetrievedChunk(
                content=chunk.content,
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                score=score,
                embedding=embedding,
            )
        )
    return chunks


def _rehydrate_cached_chunks(
    db: Session,
    query_embedding: list[float],
    chunk_keys: list[tuple[str, int]],
) -> list[RetrievedChunk] | None:
    if not chunk_keys:
        return []

    stmt = (
        select(DocumentChunk, Document.filename)
        .join(Document, DocumentChunk.document_id == Document.id)
        .where(Document.status == DocumentStatus.READY.value)
        .where(tuple_(DocumentChunk.document_id, DocumentChunk.chunk_index).in_(chunk_keys))
    )
    rows = db.execute(stmt).all()
    if len(rows) != len(chunk_keys):
        return None

    chunk_map: dict[tuple[str, int], tuple[DocumentChunk, str]] = {}
    for chunk, filename in rows:
        chunk_map[(chunk.document_id, chunk.chunk_index)] = (chunk, filename)

    chunks: list[RetrievedChunk] = []
    for document_id, chunk_index in chunk_keys:
        row = chunk_map.get((document_id, chunk_index))
        if row is None:
            return None
        chunk, filename = row
        if chunk.embedding is None:
            return None
        score = max(0.0, 1.0 - float(chunk.embedding.cosine_distance(query_embedding)))
        embedding = list(chunk.embedding)
        chunks.append(
            RetrievedChunk(
                content=chunk.content,
                document_id=chunk.document_id,
                filename=filename,
                chunk_index=chunk.chunk_index,
                page_number=chunk.page_number,
                score=score,
                embedding=embedding,
            )
        )
    return chunks


def _retrieve_with_cache(
    db: Session,
    query_embedding: list[float],
    k: int,
) -> list[RetrievedChunk]:
    cached_keys = retrieval_result_cache.get(query_embedding, k)
    if cached_keys is not None:
        chunks = _rehydrate_cached_chunks(db, query_embedding, cached_keys)
        if chunks is not None:
            logger.info(
                "retrieve_cache_hit",
                model=EMBEDDING_MODEL,
                k=k,
                hits=len(chunks),
            )
            return chunks
        logger.info("retrieve_cache_stale", model=EMBEDDING_MODEL, k=k)

    chunks = _retrieve_with_session(db, query_embedding, k)
    if chunks:
        cache_keys = [(chunk.document_id, chunk.chunk_index) for chunk in chunks]
        retrieval_result_cache.set(query_embedding, k, cache_keys)
    return chunks


def retrieve_chunks(
    query: str,
    *,
    k: int | None = None,
    query_embedding: list[float] | None = None,
) -> tuple[list[RetrievedChunk], list[float], TokenUsage | None]:
    """Return top-k chunks, the query embedding used, and optional embed usage."""
    text = query.strip()
    if not text:
        return [], [], None

    settings = get_settings()
    top_k = k if k is not None else settings.retrieval_k
    if top_k <= 0:
        return [], [], None

    embed_usage: TokenUsage | None = None
    if query_embedding is None:
        result = embed_texts_with_usage([text])
        if not result.embeddings:
            return [], [], None
        query_embedding = result.embeddings[0]
        embed_usage = result.usage

    with get_session() as db:
        chunks = _retrieve_with_cache(db, query_embedding, top_k)

    logger.info(
        "retrieve_complete",
        model=EMBEDDING_MODEL,
        k=top_k,
        hits=len(chunks),
    )
    return chunks, query_embedding, embed_usage


async def retrieve_chunks_async(
    query: str,
    *,
    k: int | None = None,
) -> tuple[list[RetrievedChunk], list[float], TokenUsage | None]:
    """Async wrapper: embed via async path, run DB fetch in a thread."""
    from rag_core.rag.embeddings import embed_texts_with_usage_async

    text = query.strip()
    if not text:
        return [], [], None

    settings = get_settings()
    top_k = k if k is not None else settings.retrieval_k
    if top_k <= 0:
        return [], [], None

    result = await embed_texts_with_usage_async([text])
    query_embedding = list(result.embeddings[0])

    chunks, embedding, _ = await asyncio.to_thread(
        retrieve_chunks,
        text,
        k=top_k,
        query_embedding=query_embedding,
    )
    return chunks, embedding, result.usage
