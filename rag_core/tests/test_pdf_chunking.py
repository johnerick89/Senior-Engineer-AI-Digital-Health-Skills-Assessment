"""Tests for rag_core.rag.pdf and rag_core.rag.chunking."""

from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest
from pypdf import PdfWriter

from rag_core.rag.chunking import CHUNK_OVERLAP, CHUNK_SIZE, TextChunk, chunk_pages, chunk_text
from rag_core.rag.pdf import PageText, PdfExtractionError, extract_pdf_pages


def _minimal_pdf_bytes(text: str = "Hello RAG") -> bytes:
    """Build a one-page PDF. Text may not survive round-trip; used for structure tests."""
    writer = PdfWriter()
    writer.add_blank_page(width=200, height=200)
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def test_chunk_text_empty_returns_empty() -> None:
    assert chunk_text("   ") == []


def test_chunk_text_basic_split() -> None:
    text = "a" * 50
    chunks = chunk_text(text, size=20, overlap=5)
    assert len(chunks) >= 2
    assert chunks[0].chunk_index == 0
    assert chunks[0].page_number is None
    assert all(isinstance(c, TextChunk) for c in chunks)


def test_chunk_text_rejects_invalid_overlap() -> None:
    with pytest.raises(ValueError, match="overlap"):
        chunk_text("hello", size=10, overlap=10)


def test_chunk_pages_preserves_page_numbers_and_global_index() -> None:
    pages = [
        PageText(page_number=1, text="a" * 30),
        PageText(page_number=2, text="b" * 30),
    ]
    chunks = chunk_pages(pages, size=20, overlap=0)
    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2
    indexes = [c.chunk_index for c in chunks]
    assert indexes == list(range(len(chunks)))


def test_chunk_constants_match_reference_defaults() -> None:
    assert CHUNK_SIZE == 1200
    assert CHUNK_OVERLAP == 150


def test_extract_pdf_pages_rejects_empty() -> None:
    with pytest.raises(PdfExtractionError, match="empty"):
        extract_pdf_pages(b"")


def test_extract_pdf_pages_rejects_invalid_bytes() -> None:
    with pytest.raises(PdfExtractionError, match="Could not read PDF"):
        extract_pdf_pages(b"not-a-pdf")


@patch("rag_core.rag.pdf.PdfReader")
def test_extract_pdf_pages_from_mocked_reader(mock_reader_cls: MagicMock) -> None:
    page1 = MagicMock()
    page1.extract_text.return_value = "Page one content"
    page2 = MagicMock()
    page2.extract_text.return_value = "Page two content"
    mock_reader_cls.return_value.pages = [page1, page2]

    pages = extract_pdf_pages(b"%PDF-fake")

    assert pages == [
        PageText(page_number=1, text="Page one content"),
        PageText(page_number=2, text="Page two content"),
    ]


@patch("rag_core.rag.pdf.PdfReader")
def test_extract_pdf_pages_rejects_all_blank(mock_reader_cls: MagicMock) -> None:
    page = MagicMock()
    page.extract_text.return_value = "   "
    mock_reader_cls.return_value.pages = [page]

    with pytest.raises(PdfExtractionError, match="no extractable text"):
        extract_pdf_pages(b"%PDF-fake")


def test_minimal_pdf_is_readable() -> None:
    """Ensure blank PDFs open; blank pages raise no-text error."""
    data = _minimal_pdf_bytes()
    with pytest.raises(PdfExtractionError, match="no extractable text"):
        extract_pdf_pages(data)
