"""PDF upload and rag_core ingestion routes."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import StreamingResponse

from app.services.upload import ingest_one, read_and_validate

router = APIRouter()


@router.post("/upload")
async def upload_pdfs(
    files: list[UploadFile] | None = File(default=None),
) -> StreamingResponse:
    """Validate PDFs, then stream NDJSON results as each file finishes ingest."""
    prepared = await read_and_validate(files or [])

    async def generate() -> AsyncIterator[str]:
        for filename, data in prepared:
            result = await asyncio.to_thread(ingest_one, filename, data)
            yield result.model_dump_json() + "\n"

    return StreamingResponse(generate(), media_type="application/x-ndjson")
