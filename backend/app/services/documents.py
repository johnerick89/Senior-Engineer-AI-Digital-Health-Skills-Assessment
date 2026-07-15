"""PDF upload validation and document management helpers."""

from __future__ import annotations

import logging
import math
import uuid

from fastapi import HTTPException, UploadFile

from app.schemas.documents import DocumentOut, UploadFileResult
from rag_core.db.session import get_session
from rag_core.rag.ingestion import ingest_pdf
from rag_core.services import document_service

logger = logging.getLogger(__name__)

MAX_FILE_SIZE_BYTES = 20 * 1024 * 1024  # 20MB, matches frontend copy


def is_pdf(upload: UploadFile) -> bool:
    """Return True when the upload looks like a PDF."""
    name = (upload.filename or "").lower()
    content_type = (upload.content_type or "").lower()
    return name.endswith(".pdf") or content_type in {
        "application/pdf",
        "application/x-pdf",
    }


async def read_and_validate(
    uploads: list[UploadFile],
) -> list[tuple[str, bytes]]:
    """Validate batch and return (filename, bytes) pairs.

    Raises HTTPException(400) before any ingest starts.
    """
    if not uploads:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    prepared: list[tuple[str, bytes]] = []
    for upload in uploads:
        filename = upload.filename or "upload.pdf"
        if not is_pdf(upload):
            raise HTTPException(
                status_code=400,
                detail=f"Only PDF files are supported. Invalid file: {filename}",
            )
        data = await upload.read()
        if len(data) == 0:
            raise HTTPException(
                status_code=400,
                detail=f"File is empty: {filename}",
            )
        if len(data) > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds 20MB limit: {filename}",
            )
        if not filename.lower().endswith(".pdf"):
            filename = f"{filename}.pdf"
        prepared.append((filename, data))

    return prepared


def ingest_one(filename: str, data: bytes) -> UploadFileResult:
    """Sync helper for asyncio.to_thread."""
    try:
        result = ingest_pdf(data, filename=filename)
        return UploadFileResult(
            filename=filename,
            document_id=str(result.document_id),
            status="ready",
            chunk_count=result.chunk_count,
            error=None,
        )
    except Exception as exc:  # noqa: BLE001 — surface to UI, keep batch going
        logger.exception("ingest_failed filename=%s", filename)
        return UploadFileResult(
            filename=filename,
            document_id=None,
            status="failed",
            chunk_count=0,
            error=str(exc),
        )


def size_bytes_to_kb(size_bytes: int | None) -> int:
    """Convert byte length to whole KB for API responses."""
    if not size_bytes or size_bytes <= 0:
        return 0
    return max(1, math.ceil(size_bytes / 1024))


def list_documents() -> list[DocumentOut]:
    """Load documents newest-first with chunk counts."""
    with get_session() as db:
        items = document_service.list_documents(db)
        return [
            DocumentOut(
                id=item.id,
                filename=item.filename,
                status=item.status,
                size_kb=size_bytes_to_kb(item.size_bytes),
                chunk_count=item.chunk_count,
                uploaded_at=item.uploaded_at,
                error_message=item.error_message,
            )
            for item in items
        ]


def delete_document(document_id: uuid.UUID) -> bool:
    """Delete a document and cascaded chunks. Return False if missing."""
    with get_session() as db:
        deleted = document_service.delete_document(db, document_id)
        if deleted:
            db.commit()
        return deleted
