"""PDF text extraction helpers."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from pypdf import PdfReader


@dataclass(frozen=True)
class PageText:
    """Plain text extracted from a single PDF page (1-based page number)."""

    page_number: int
    text: str


class PdfExtractionError(ValueError):
    """Raised when a PDF cannot be read or yields no extractable text."""


def extract_pdf_pages(data: bytes) -> list[PageText]:
    """Extract text from each page of a PDF.

    Raises:
        PdfExtractionError: if the bytes are empty or not a readable PDF.
    """
    if not data:
        raise PdfExtractionError("PDF data is empty")

    try:
        reader = PdfReader(BytesIO(data))
    except Exception as exc:  # noqa: BLE001 — pypdf raises varied exceptions
        raise PdfExtractionError(f"Could not read PDF: {exc}") from exc

    pages: list[PageText] = []
    for index, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception as exc:  # noqa: BLE001
            raise PdfExtractionError(
                f"Could not extract text from page {index}: {exc}"
            ) from exc
        pages.append(PageText(page_number=index, text=text.strip()))

    if not any(page.text for page in pages):
        raise PdfExtractionError("PDF contained no extractable text")

    return pages
