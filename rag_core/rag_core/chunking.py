"""Character-based chunking for RAG ingestion.

Chunk size and overlap are intentionally pinned (not env-configurable) so
changes require an explicit code review — large shifts affect retrieval quality.
"""

from __future__ import annotations

from dataclasses import dataclass

from rag_core.pdf import PageText

# Match litigation-prep-assistant defaults (character-based, overlapping).
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


@dataclass(frozen=True)
class TextChunk:
    """A chunk ready for embedding and storage."""

    chunk_index: int
    content: str
    page_number: int | None


def chunk_text(
    text: str,
    *,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
    page_number: int | None = None,
    start_index: int = 0,
) -> list[TextChunk]:
    """Split text into overlapping character-based chunks."""
    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be >= 0 and < size")

    if not text.strip():
        return []

    chunks: list[TextChunk] = []
    start = 0
    index = start_index
    while start < len(text):
        end = min(start + size, len(text))
        piece = text[start:end].strip()
        if piece:
            chunks.append(
                TextChunk(chunk_index=index, content=piece, page_number=page_number)
            )
            index += 1
        if end >= len(text):
            break
        start += size - overlap
    return chunks


def chunk_pages(
    pages: list[PageText],
    *,
    size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[TextChunk]:
    """Chunk each page independently, preserving page_number and a global chunk_index."""
    all_chunks: list[TextChunk] = []
    next_index = 0
    for page in pages:
        page_chunks = chunk_text(
            page.text,
            size=size,
            overlap=overlap,
            page_number=page.page_number,
            start_index=next_index,
        )
        all_chunks.extend(page_chunks)
        next_index += len(page_chunks)
    return all_chunks
