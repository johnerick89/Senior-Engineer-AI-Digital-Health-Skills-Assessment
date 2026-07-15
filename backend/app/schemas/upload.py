"""Upload response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class UploadFileResult(BaseModel):
    """One NDJSON line emitted after a PDF finishes ingest (or fails)."""

    filename: str
    document_id: str | None = None
    status: str = Field(description="ready | failed")
    chunk_count: int = 0
    error: str | None = None
