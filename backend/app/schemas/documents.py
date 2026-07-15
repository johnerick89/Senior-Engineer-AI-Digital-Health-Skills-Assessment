"""Document upload and list schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class UploadFileResult(BaseModel):
    """One NDJSON line emitted after a PDF finishes ingest (or fails)."""

    filename: str
    document_id: str | None = None
    status: str = Field(description="ready | failed")
    chunk_count: int = 0
    error: str | None = None


class DocumentOut(BaseModel):
    """Single document row for GET /documents."""

    id: uuid.UUID
    filename: str
    status: str = Field(description="ready | processing | failed")
    size_kb: int
    chunk_count: int
    uploaded_at: datetime
    error_message: str | None = None
