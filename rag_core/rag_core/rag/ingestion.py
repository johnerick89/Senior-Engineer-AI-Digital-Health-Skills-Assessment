"""PDF ingest pipeline: extract → chunk → embed → store."""

from __future__ import annotations

import uuid
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel, Field

from rag_core.core.logging import get_logger
from rag_core.db.session import get_session
from rag_core.models.document import DocumentStatus
from rag_core.models.usage_event import UsageKind
from rag_core.rag.chunking import chunk_pages
from rag_core.rag.embeddings import EMBEDDING_MODEL, embed_texts_with_usage
from rag_core.rag.pdf import PdfExtractionError, extract_pdf_pages
from rag_core.services.document_service import (
    ChunkInsert,
    create_document,
    insert_chunks,
    update_document_status,
)
from rag_core.core.token_usage import apportion_integers
from rag_core.services.usage_service import record_usage_event

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
        document = create_document(
            db,
            resolved_name,
            status=DocumentStatus.PROCESSING.value,
            size_bytes=len(data),
        )
        db.commit()
        document_id = document.id

    logger.info("ingest_started", document_id=str(document_id), filename=resolved_name)

    try:
        pages = extract_pdf_pages(data)
        chunks = chunk_pages(pages)
        if not chunks:
            raise PdfExtractionError("No text chunks produced from PDF")

        texts = [chunk.content for chunk in chunks]
        embed_result = embed_texts_with_usage(texts)
        embeddings = embed_result.embeddings
        if len(embeddings) != len(chunks):
            raise RuntimeError(
                f"Embedding count mismatch: {len(embeddings)} vectors for {len(chunks)} chunks"
            )

        weights = [max(1, len(t)) for t in texts]
        token_parts = apportion_integers(embed_result.usage.prompt_tokens, weights)
        total_cost = embed_result.usage.estimated_cost_usd
        cost_parts = apportion_integers(
            int(total_cost * Decimal("100000000")),  # 1e-8 USD units
            weights,
        )

        inserts = [
            ChunkInsert(
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                page_number=chunk.page_number,
                embedding=embeddings[i],
                prompt_tokens=token_parts[i],
                estimated_cost_usd=Decimal(cost_parts[i]) / Decimal("100000000"),
                model=EMBEDDING_MODEL,
            )
            for i, chunk in enumerate(chunks)
        ]

        with get_session() as db:
            insert_chunks(db, document_id, inserts)
            update_document_status(db, document_id, DocumentStatus.READY.value)
            record_usage_event(
                db,
                kind=UsageKind.INGEST_EMBEDDING,
                usage=embed_result.usage,
                document_id=document_id,
            )
            db.commit()

        logger.info(
            "ingest_complete",
            document_id=str(document_id),
            chunk_count=len(inserts),
            embed_tokens=embed_result.usage.prompt_tokens,
            embed_cost_usd=float(embed_result.usage.estimated_cost_usd),
        )
        return IngestResult(
            document_id=document_id,
            filename=resolved_name,
            chunk_count=len(inserts),
        )
    except Exception as exc:
        logger.exception("ingest_failed", document_id=str(document_id), filename=resolved_name)
        try:
            with get_session() as db:
                update_document_status(
                    db,
                    document_id,
                    DocumentStatus.FAILED.value,
                    error_message=str(exc)[:2000],
                )
                db.commit()
        except Exception:  # noqa: BLE001
            logger.exception("ingest_status_update_failed", document_id=str(document_id))
        raise
