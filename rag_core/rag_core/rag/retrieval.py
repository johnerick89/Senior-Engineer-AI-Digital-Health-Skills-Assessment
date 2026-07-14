"""Vector similarity search over document_chunks (pgvector cosine)."""

from __future__ import annotations

import asyncio

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_core.core.config import get_settings
from rag_core.core.logging import get_logger
from rag_core.db.session import get_session
from rag_core.models.document import Document, DocumentStatus
from rag_core.models.document_chunk import DocumentChunk
from rag_core.rag.embeddings import EMBEDDING_MODEL, embed_texts
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


def retrieve_chunks(
    query: str,
    *,
    k: int | None = None,
    query_embedding: list[float] | None = None,
) -> tuple[list[RetrievedChunk], list[float]]:
    """Return top-k chunks by cosine distance and the query embedding used.

    If ``query_embedding`` is provided, embedding generation is skipped.
    """
    text = query.strip()
    if not text:
        return [], []

    settings = get_settings()
    top_k = k if k is not None else settings.retrieval_k
    if top_k <= 0:
        return [], []

    if query_embedding is None:
        vectors = embed_texts([text])
        if not vectors:
            return [], []
        query_embedding = vectors[0]

    with get_session() as db:
        chunks = _retrieve_with_session(db, query_embedding, top_k)

    logger.info(
        "retrieve_complete",
        model=EMBEDDING_MODEL,
        k=top_k,
        hits=len(chunks),
    )
    return chunks, query_embedding


async def retrieve_chunks_async(
    query: str,
    *,
    k: int | None = None,
) -> tuple[list[RetrievedChunk], list[float]]:
    """Async wrapper: embed via async path, run DB fetch in a thread."""
    from rag_core.core.openai_client import create_embeddings
    from rag_core.rag.embeddings import EMBEDDING_MODEL as MODEL

    text = query.strip()
    if not text:
        return [], []

    settings = get_settings()
    top_k = k if k is not None else settings.retrieval_k
    if top_k <= 0:
        return [], []

    response = await create_embeddings(model=MODEL, input=[text])
    query_embedding = list(response.data[0].embedding)

    return await asyncio.to_thread(
        retrieve_chunks,
        text,
        k=top_k,
        query_embedding=query_embedding,
    )
