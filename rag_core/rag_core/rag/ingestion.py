"""PDF ingest pipeline: extract → chunk → embed → store."""

from __future__ import annotations

import uuid
from pathlib import Path

from pydantic import BaseModel, Field

from rag_core.core.logging import get_logger
from rag_core.db.session import get_session
from rag_core.models.document import DocumentStatus
from rag_core.rag.chunking import chunk_pages
from rag_core.rag.embeddings import embed_texts
from rag_core.rag.pdf import PdfExtractionError, extract_pdf_pages
from rag_core.services.document_service import (
    ChunkInsert,
    create_document,
    insert_chunks,
    update_document_status,
)

logger = get_logger(__name__)


class IngestResult(BaseModel):
    """Result of a successful PDF ingest."""

    document_id: uuid.UUID
    filename: str
    chunk_count: int = Field(ge=0)


def ingest_pdf(
    source: Path | bytes,
    *,
    filename: str | None = None,
) -> IngestResult:
    """Extract, chunk, embed, and store a PDF.

    Args:
        source: Path to a PDF file, or raw PDF bytes.
        filename: Required when ``source`` is bytes; otherwise defaults to the path name.
    """
    if isinstance(source, Path):
        data = source.read_bytes()
        resolved_name = filename or source.name
    else:
        data = source
        if not filename:
            raise ValueError("filename is required when ingesting PDF bytes")
        resolved_name = filename

    if not resolved_name.lower().endswith(".pdf"):
        raise PdfExtractionError(f"Only PDF files are supported, got: {resolved_name}")

    with get_session() as db:
        document = create_document(db, resolved_name, status=DocumentStatus.PROCESSING.value)
        db.commit()
        document_id = document.id

    logger.info("ingest_started", document_id=str(document_id), filename=resolved_name)

    try:
        pages = extract_pdf_pages(data)
        chunks = chunk_pages(pages)
        if not chunks:
            raise PdfExtractionError("No text chunks produced from PDF")

        embeddings = embed_texts([chunk.content for chunk in chunks])
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: {len(embeddings)} vectors for {len(chunks)} chunks"
            )

        inserts = [
            ChunkInsert(
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                embedding=embeddings[i],
            )
            for i, chunk in enumerate(chunks)
        ]

        with get_session() as db:
            insert_chunks(db, document_id, inserts)
            update_document_status(db, document_id, DocumentStatus.READY.value)
            db.commit()

        logger.info(
            "ingest_complete",
            document_id=str(document_id),
            chunk_count=len(inserts),
        )
        return IngestResult(
            document_id=document_id,
            filename=resolved_name,
            chunk_count=len(inserts),
        )
    except Exception:
        logger.exception("ingest_failed", document_id=str(document_id), filename=resolved_name)
        try:
            with get_session() as db:
                update_document_status(db, document_id, DocumentStatus.FAILED.value)
                db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("ingest_status_update_failed", document_id=str(document_id))
        raise
