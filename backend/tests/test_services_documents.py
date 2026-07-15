"""Unit tests for app.services.documents helpers."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.documents import (
    MAX_FILE_SIZE_BYTES,
    ingest_one,
    is_pdf,
    read_and_validate,
    size_bytes_to_kb,
)


def _upload(*, filename: str, content_type: str, data: bytes) -> MagicMock:
    upload = MagicMock()
    upload.filename = filename
    upload.content_type = content_type
    upload.read = AsyncMock(return_value=data)
    return upload


def test_is_pdf_by_extension() -> None:
    upload = _upload(filename="a.pdf", content_type="application/octet-stream", data=b"x")
    assert is_pdf(upload) is True


def test_is_pdf_by_content_type() -> None:
    upload = _upload(filename="a", content_type="application/pdf", data=b"x")
    assert is_pdf(upload) is True


def test_is_pdf_rejects_text() -> None:
    upload = _upload(filename="a.txt", content_type="text/plain", data=b"x")
    assert is_pdf(upload) is False


@pytest.mark.asyncio
async def test_read_and_validate_ok() -> None:
    upload = _upload(filename="doc.pdf", content_type="application/pdf", data=b"%PDF")
    prepared = await read_and_validate([upload])
    assert prepared == [("doc.pdf", b"%PDF")]


@pytest.mark.asyncio
async def test_read_and_validate_empty_batch() -> None:
    with pytest.raises(HTTPException) as exc:
        await read_and_validate([])
    assert exc.value.status_code == 400


@pytest.mark.asyncio
async def test_read_and_validate_oversize() -> None:
    upload = _upload(
        filename="big.pdf",
        content_type="application/pdf",
        data=b"x" * (MAX_FILE_SIZE_BYTES + 1),
    )
    with pytest.raises(HTTPException) as exc:
        await read_and_validate([upload])
    assert exc.value.status_code == 400
    assert "20MB" in str(exc.value.detail)


def test_ingest_one_ready() -> None:
    result = MagicMock()
    result.document_id = "11111111-1111-1111-1111-111111111111"
    result.chunk_count = 2
    with patch("app.services.documents.ingest_pdf", return_value=result):
        out = ingest_one("a.pdf", b"%PDF")
    assert out.status == "ready"
    assert out.chunk_count == 2
    assert out.document_id == "11111111-1111-1111-1111-111111111111"
    assert out.error is None


def test_ingest_one_failed() -> None:
    with patch(
        "app.services.documents.ingest_pdf",
        side_effect=RuntimeError("parse failed"),
    ):
        out = ingest_one("a.pdf", b"%PDF")
    assert out.status == "failed"
    assert out.chunk_count == 0
    assert out.document_id is None
    assert "parse failed" in (out.error or "")


def test_size_bytes_to_kb() -> None:
    assert size_bytes_to_kb(None) == 0
    assert size_bytes_to_kb(0) == 0
    assert size_bytes_to_kb(1) == 1
    assert size_bytes_to_kb(1024) == 1
    assert size_bytes_to_kb(1025) == 2
