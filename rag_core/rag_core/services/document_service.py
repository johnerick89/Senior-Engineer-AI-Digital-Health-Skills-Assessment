"""Document persistence via SQLAlchemy ORM."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_core.rag.embeddings import EMBEDDING_DIMENSION
from rag_core.models.document import Document, DocumentStatus
from rag_core.models.document_chunk import DocumentChunk


@dataclass(frozen=True)
class ChunkInsert:
    """One chunk row to insert."""

    chunk_index: int
    content: str
    page_number: int | None
    embedding: list[float]


def create_document(
    db: Session,
    filename: str,
    *,
    status: str = DocumentStatus.PROCESSING.value,
) -> Document:
    """Insert a documents row and return the ORM instance (flushed, not committed)."""
    document = Document(filename=filename, status=status)
    db.add(document)
    db.flush()
    return document


def insert_chunks(
    db: Session,
    document_id: uuid.UUID,
    chunks: Sequence[ChunkInsert],
) -> int:
    """Batch-insert document_chunks with embeddings. Returns inserted count."""
    if not chunks:
        return 0

    for chunk in chunks:
        if len(chunk.embedding) != EMBEDDING_DIMENSION:
            raise ValueError(
                f"chunk {chunk.chunk_index}: expected embedding dim "
                f"{EMBEDDING_DIMENSION}, got {len(chunk.embedding)}"
            )
        db.add(
            DocumentChunk(
                document_id=document_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                embedding=chunk.embedding,
            )
        )

    db.flush()
    return len(chunks)


def update_document_status(
    db: Session,
    document_id: uuid.UUID,
    status: str,
) -> Document:
    """Update documents.status. Raises LookupError if the row is missing."""
    document = db.get(Document, document_id)
    if document is None:
        raise LookupError(f"document {document_id} not found")
    document.status = status
    db.flush()
    return document


def get_document(db: Session, document_id: uuid.UUID) -> Document | None:
    """Return a document by id, or None."""
    return db.get(Document, document_id)


def list_ready_document_filenames(
    db: Session,
    *,
    limit: int = 10,
) -> list[str]:
    """Return up to ``limit`` filenames for documents with status ready."""
    if limit <= 0:
        return []

    stmt = (
        select(Document.filename)
        .where(Document.status == DocumentStatus.READY.value)
        .distinct()
        .order_by(Document.filename)
        .limit(limit)
    )
    return list(db.scalars(stmt).all())
