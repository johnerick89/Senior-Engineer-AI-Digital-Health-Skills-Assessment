"""Tests for rag_core.rag.ingestion.ingest_pdf."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rag_core.models.document import Document, DocumentStatus
from rag_core.rag.chunking import TextChunk
from rag_core.rag.embeddings import EMBEDDING_DIMENSION
from rag_core.rag.ingestion import IngestResult, ingest_pdf
from rag_core.rag.pdf import PageText, PdfExtractionError


def _session_cm(db: MagicMock) -> MagicMock:
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None
    return cm


@patch("rag_core.rag.ingestion.get_session")
@patch("rag_core.rag.ingestion.record_usage_event")
@patch("rag_core.rag.ingestion.update_document_status")
@patch("rag_core.rag.ingestion.insert_chunks")
@patch("rag_core.rag.ingestion.embed_texts_with_usage")
@patch("rag_core.rag.ingestion.chunk_pages")
@patch("rag_core.rag.ingestion.extract_pdf_pages")
@patch("rag_core.rag.ingestion.create_document")
def test_ingest_pdf_happy_path(
    mock_create: MagicMock,
    mock_extract: MagicMock,
    mock_chunk: MagicMock,
    mock_embed: MagicMock,
    mock_insert: MagicMock,
    mock_status: MagicMock,
    mock_record: MagicMock,
    mock_get_session: MagicMock,
) -> None:
    from rag_core.rag.embeddings import EmbeddingResult
    from rag_core.services.usage_service import TokenUsage

    document_id = uuid.uuid4()
    document = Document(filename="doc.pdf", status=DocumentStatus.PROCESSING.value)
    document.id = document_id
    mock_create.return_value = document
    mock_extract.return_value = [PageText(1, "hello")]
    mock_chunk.return_value = [TextChunk(0, "hello", 1)]
    mock_embed.return_value = EmbeddingResult(
        embeddings=[[0.1] * EMBEDDING_DIMENSION],
        usage=TokenUsage(
            prompt_tokens=2,
            model="text-embedding-3-small",
            is_embedding=True,
        ),
    )

    db1 = MagicMock()
    db2 = MagicMock()
    mock_get_session.side_effect = [_session_cm(db1), _session_cm(db2)]

    result = ingest_pdf(b"%PDF-1.4", filename="doc.pdf")

    assert result == IngestResult(document_id=document_id, filename="doc.pdf", chunk_count=1)
    mock_status.assert_called_with(db2, document_id, DocumentStatus.READY.value)
    mock_record.assert_called_once()
    db2.commit.assert_called_once()


def test_ingest_pdf_bytes_requires_filename() -> None:
    with pytest.raises(ValueError, match="filename is required"):
        ingest_pdf(b"%PDF")


def test_ingest_pdf_rejects_non_pdf_filename() -> None:
    with pytest.raises(PdfExtractionError, match="Only PDF"):
        ingest_pdf(b"%PDF", filename="notes.txt")


@patch("rag_core.rag.ingestion.get_session")
@patch("rag_core.rag.ingestion.update_document_status")
@patch("rag_core.rag.ingestion.create_document")
@patch("rag_core.rag.ingestion.extract_pdf_pages", side_effect=PdfExtractionError("bad pdf"))
def test_ingest_pdf_marks_failed_on_error(
    _mock_extract: MagicMock,
    mock_create: MagicMock,
    mock_status: MagicMock,
    mock_get_session: MagicMock,
) -> None:
    document_id = uuid.uuid4()
    document = Document(filename="bad.pdf", status=DocumentStatus.PROCESSING.value)
    document.id = document_id
    mock_create.return_value = document

    db1 = MagicMock()
    db_fail = MagicMock()
    mock_get_session.side_effect = [_session_cm(db1), _session_cm(db_fail)]

    with pytest.raises(PdfExtractionError):
        ingest_pdf(b"%PDF", filename="bad.pdf")

    mock_status.assert_called_with(db_fail, document_id, DocumentStatus.FAILED.value)


@patch("rag_core.rag.ingestion.ingest_pdf")
def test_cli_ingest_invokes_pipeline(
    mock_ingest: MagicMock,
    tmp_path: Path,
) -> None:
    from rag_core.__main__ import cmd_ingest

    pdf = tmp_path / "sample.pdf"
    pdf.write_bytes(b"%PDF-1.4")
    mock_ingest.return_value = IngestResult(
        document_id=uuid.uuid4(),
        filename="sample.pdf",
        chunk_count=3,
    )

    cmd_ingest(pdf)

    mock_ingest.assert_called_once_with(pdf, filename="sample.pdf")


@pytest.mark.integration
def test_ingest_pdf_integration_with_fake_embeddings(
    integration_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end against Postgres; OpenAI is mocked."""
    from rag_core.core.config import Settings, get_settings
    from rag_core.rag.vector_store import initialize_vector_store

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", integration_database_url)
    get_settings.cache_clear()
    settings = Settings(_env_file=None, database_url=integration_database_url)
    initialize_vector_store(settings=settings)

    page = MagicMock()
    page.extract_text.return_value = "Integration test content for RAG ingestion."

    with (
        patch("rag_core.rag.pdf.PdfReader") as mock_reader,
        patch(
            "rag_core.rag.ingestion.embed_texts_with_usage",
        ) as mock_embed,
    ):
        from rag_core.rag.embeddings import EmbeddingResult
        from rag_core.services.usage_service import TokenUsage

        mock_embed.return_value = EmbeddingResult(
            embeddings=[[0.01] * EMBEDDING_DIMENSION],
            usage=TokenUsage(
                prompt_tokens=8,
                model="text-embedding-3-small",
                is_embedding=True,
            ),
        )
        mock_reader.return_value.pages = [page]
        result = ingest_pdf(b"%PDF-fake", filename="integration.pdf")

    assert result.chunk_count >= 1
    assert result.filename == "integration.pdf"
