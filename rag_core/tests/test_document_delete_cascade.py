"""Integration: deleting a document cascades chunks/embeddings."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rag_core.rag.embeddings import EMBEDDING_DIMENSION
from rag_core.rag.ingestion import ingest_pdf
from rag_core.services import document_service


@pytest.mark.integration
def test_delete_document_cascades_chunks(
    integration_database_url: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DELETE documents row must leave zero document_chunks for that id."""
    from rag_core.core.config import Settings, get_settings
    from rag_core.db.session import get_session
    from rag_core.rag.vector_store import initialize_vector_store

    get_settings.cache_clear()
    monkeypatch.setenv("DATABASE_URL", integration_database_url)
    get_settings.cache_clear()
    settings = Settings(_env_file=None, database_url=integration_database_url)
    initialize_vector_store(settings=settings)

    page = MagicMock()
    page.extract_text.return_value = "Cascade delete integration content."

    with (
        patch("rag_core.rag.pdf.PdfReader") as mock_reader,
        patch("rag_core.rag.ingestion.embed_texts_with_usage") as mock_embed,
    ):
        from rag_core.rag.embeddings import EmbeddingResult
        from rag_core.services.usage_service import TokenUsage

        mock_embed.return_value = EmbeddingResult(
            embeddings=[[0.02] * EMBEDDING_DIMENSION],
            usage=TokenUsage(
                prompt_tokens=4,
                model="text-embedding-3-small",
                is_embedding=True,
            ),
        )
        mock_reader.return_value.pages = [page]
        result = ingest_pdf(b"%PDF-cascade", filename="cascade.pdf")

    document_id = result.document_id
    assert result.chunk_count >= 1

    with get_session() as db:
        assert document_service.count_chunks_for_document(db, document_id) >= 1
        assert document_service.delete_document(db, document_id) is True
        db.commit()
        assert document_service.count_chunks_for_document(db, document_id) == 0
        assert document_service.get_document(db, document_id) is None
