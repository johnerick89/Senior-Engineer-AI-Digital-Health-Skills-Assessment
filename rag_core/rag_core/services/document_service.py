"""Document persistence via SQLAlchemy ORM."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_core.models.document import Document, DocumentStatus
from rag_core.models.document_chunk import DocumentChunk
from rag_core.rag.embeddings import EMBEDDING_DIMENSION


@dataclass(frozen=True)
class ChunkInsert:
    """One chunk row to insert."""

    chunk_index: int
    content: str
    page_number: int | None
    embedding: list[float]
    prompt_tokens: int | None = None
    estimated_cost_usd: object | None = None
    model: str | None = None


@dataclass(frozen=True)
class DocumentListItem:
    """Document row plus chunk count for API list responses."""

    id: uuid.UUID
    filename: str
    status: str
    size_bytes: int | None
    chunk_count: int
    uploaded_at: datetime
    error_message: str | None


def create_document(
    db: Session,
    filename: str,
    *,
    status: str = DocumentStatus.PROCESSING.value,
    size_bytes: int | None = None,
) -> Document:
    """Insert a documents row and return the ORM instance (flushed, not committed)."""
    document = Document(
        filename=filename,
        status=status,
        size_bytes=size_bytes,
    )
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
                prompt_tokens=chunk.prompt_tokens,
                estimated_cost_usd=chunk.estimated_cost_usd,
                model=chunk.model,
            )
        )

    db.flush()
    return len(chunks)


def update_document_status(
    db: Session,
    document_id: uuid.UUID,
    status: str,
    *,
    error_message: str | None = None,
) -> Document:
    """Update documents.status (and optional error_message).

    Ready status clears ``error_message``. Failed status stores
    ``error_message`` when provided. Raises LookupError if missing.
    """
    document = db.get(Document, document_id)
    if document is None:
        raise LookupError(f"document {document_id} not found")
    document.status = status
    if status == DocumentStatus.READY.value:
        document.error_message = None
    elif error_message is not None:
        document.error_message = error_message
    db.flush()
    return document


def get_document(db: Session, document_id: uuid.UUID) -> Document | None:
    """Return a document by id, or None."""
    return db.get(Document, document_id)


def list_documents(db: Session) -> list[DocumentListItem]:
    """Return all documents newest-first, with chunk counts."""
    chunk_count = func.count(DocumentChunk.id).label("chunk_count")
    stmt = (
        select(Document, chunk_count)
        .outerjoin(DocumentChunk, DocumentChunk.document_id == Document.id)
        .group_by(Document.id)
        .order_by(Document.created_at.desc())
    )
    rows = db.execute(stmt).all()
    return [
        DocumentListItem(
            id=document.id,
            filename=document.filename,
            status=document.status,
            size_bytes=document.size_bytes,
            chunk_count=int(count or 0),
            uploaded_at=document.created_at,
            error_message=document.error_message,
        )
        for document, count in rows
    ]


def delete_document(db: Session, document_id: uuid.UUID) -> bool:
    """Delete a document (chunks cascade via FK). Return False if missing."""
    document = db.get(Document, document_id)
    if document is None:
        return False
    db.delete(document)
    db.flush()
    return True


def count_chunks_for_document(db: Session, document_id: uuid.UUID) -> int:
    """Return the number of chunks for a document id."""
    stmt = (
        select(func.count())
        .select_from(DocumentChunk)
        .where(DocumentChunk.document_id == document_id)
    )
    return int(db.scalar(stmt) or 0)


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


@dataclass(frozen=True)
class DocumentSnippet:
    """A short content sample from a ready document."""

    filename: str
    content: str
    page_number: int | None


def sample_ready_document_snippets(
    db: Session,
    *,
    limit: int = 8,
    max_chars: int = 400,
) -> list[DocumentSnippet]:
    """Return one early chunk per ready document (up to ``limit`` docs)."""
    if limit <= 0:
        return []

    docs_stmt = (
        select(Document)
        .where(Document.status == DocumentStatus.READY.value)
        .order_by(Document.updated_at.desc())
        .limit(limit)
    )
    documents = list(db.scalars(docs_stmt).all())
    snippets: list[DocumentSnippet] = []

    for document in documents:
        chunk_stmt = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document.id)
            .where(DocumentChunk.content.is_not(None))
            .order_by(DocumentChunk.chunk_index.asc())
            .limit(1)
        )
        chunk = db.scalars(chunk_stmt).first()
        if chunk is None:
            continue
        text = " ".join(chunk.content.split()).strip()
        if not text:
            continue
        if len(text) > max_chars:
            text = text[: max_chars - 1].rstrip() + "…"
        snippets.append(
            DocumentSnippet(
                filename=document.filename,
                content=text,
                page_number=chunk.page_number,
            )
        )
    return snippets
