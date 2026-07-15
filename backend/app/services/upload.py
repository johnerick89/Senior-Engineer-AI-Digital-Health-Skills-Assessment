"""PDF upload validation and ingest helpers."""

from __future__ import annotations

import logging

from fastapi import HTTPException, UploadFile

from app.schemas.upload import UploadFileResult
from rag_core.rag.ingestion import ingest_pdf

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
