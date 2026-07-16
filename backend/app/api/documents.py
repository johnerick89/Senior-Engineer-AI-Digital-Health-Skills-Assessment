"""Document collection: upload, list, delete."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse

from app.core.rate_limiter import limiter
from app.schemas.documents import DocumentOut
from app.services.documents import (
    delete_document,
    ingest_one,
    list_documents,
    read_and_validate,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.post("")
@limiter.limit("10/minute")
async def create_documents(
    request: Request,
    files: list[UploadFile] | None = File(default=None),
) -> StreamingResponse:
    """Validate PDFs, then stream NDJSON results as each file finishes ingest."""
    del request
    prepared = await read_and_validate(files or [])

    async def generate() -> AsyncIterator[str]:
        for filename, data in prepared:
            result = await asyncio.to_thread(ingest_one, filename, data)
            yield result.model_dump_json() + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")


@router.get("", response_model=list[DocumentOut])
async def get_documents() -> list[DocumentOut]:
    """Return ingested documents newest-first."""
    return await asyncio.to_thread(list_documents)


@router.delete("/{document_id}", status_code=204)
async def remove_document(document_id: uuid.UUID) -> Response:
    """Delete a document; chunks/embeddings cascade via FK."""

    def _delete() -> bool:
        return delete_document(document_id)

    deleted = await asyncio.to_thread(_delete)
    if not deleted:
        raise HTTPException(status_code=404, detail="Document not found")
    return Response(status_code=204)
