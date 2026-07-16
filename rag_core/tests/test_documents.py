"""Tests for rag_core.services.document_service."""

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from rag_core.models.document import Document, DocumentStatus
from rag_core.rag.embeddings import EMBEDDING_DIMENSION
from rag_core.services.document_service import (
    ChunkInsert,
    create_document,
    delete_document,
    insert_chunks,
    list_documents,
    update_document_status,
)


def _fake_embedding() -> list[float]:
    return [0.1] * EMBEDDING_DIMENSION


def test_create_document_adds_and_flushes() -> None:
    db = MagicMock()

    document = create_document(db, "guide.pdf", size_bytes=2048)

    assert isinstance(document, Document)
    assert document.filename == "guide.pdf"
    assert document.status == DocumentStatus.PROCESSING.value
    assert document.size_bytes == 2048
    db.add.assert_called_once_with(document)
    db.flush.assert_called_once()


def test_insert_chunks_adds_orm_rows() -> None:
    db = MagicMock()
    document_id = uuid.uuid4()
    chunks = [
        ChunkInsert(
            chunk_index=0,
            content="hello",
            page_number=1,
            embedding=_fake_embedding(),
        )
    ]

    count = insert_chunks(db, document_id, chunks)

    assert count == 1
    assert db.add.call_count == 1
    db.flush.assert_called_once()


def test_insert_chunks_rejects_wrong_dimension() -> None:
    with pytest.raises(ValueError, match="embedding dim"):
        insert_chunks(
            MagicMock(),
            uuid.uuid4(),
            [
                ChunkInsert(
                    chunk_index=0,
                    content="x",
                    page_number=None,
                    embedding=[0.1, 0.2],
                )
            ],
        )


def test_update_document_status_updates_orm_instance() -> None:
    db = MagicMock()
    document_id = uuid.uuid4()
    document = Document(filename="a.pdf", status=DocumentStatus.PROCESSING.value)
    document.id = document_id
    db.get.return_value = document

    updated = update_document_status(db, document_id, DocumentStatus.READY.value)

    assert updated.status == DocumentStatus.READY.value
    db.flush.assert_called_once()


def test_update_document_status_missing_raises() -> None:
    db = MagicMock()
    db.get.return_value = None

    with pytest.raises(LookupError, match="not found"):
        update_document_status(db, uuid.uuid4(), DocumentStatus.FAILED.value)


def test_update_document_status_failed_stores_error() -> None:
    db = MagicMock()
    document_id = uuid.uuid4()
    document = Document(filename="a.pdf", status=DocumentStatus.PROCESSING.value)
    document.id = document_id
    db.get.return_value = document

    updated = update_document_status(
        db,
        document_id,
        DocumentStatus.FAILED.value,
        error_message="parse failed",
    )

    assert updated.status == DocumentStatus.FAILED.value
    assert updated.error_message == "parse failed"


def test_update_document_status_ready_clears_error() -> None:
    db = MagicMock()
    document_id = uuid.uuid4()
    document = Document(
        filename="a.pdf",
        status=DocumentStatus.FAILED.value,
        error_message="old",
    )
    document.id = document_id
    db.get.return_value = document

    updated = update_document_status(db, document_id, DocumentStatus.READY.value)

    assert updated.error_message is None


def test_delete_document_returns_false_when_missing() -> None:
    db = MagicMock()
    db.get.return_value = None

    assert delete_document(db, uuid.uuid4()) is False
    db.delete.assert_not_called()


def test_delete_document_deletes_row() -> None:
    db = MagicMock()
    document_id = uuid.uuid4()
    document = Document(filename="gone.pdf", status=DocumentStatus.READY.value)
    document.id = document_id
    db.get.return_value = document

    assert delete_document(db, document_id) is True
    db.delete.assert_called_once_with(document)
    db.flush.assert_called_once()


def test_list_documents_maps_rows() -> None:
    db = MagicMock()
    document_id = uuid.uuid4()
    uploaded_at = datetime(2026, 7, 13, 10, 22, tzinfo=timezone.utc)
    document = Document(
        filename="training_manual.pdf",
        status=DocumentStatus.READY.value,
        size_bytes=2380 * 1024,
        error_message=None,
    )
    document.id = document_id
    document.created_at = uploaded_at
    db.execute.return_value.all.return_value = [(document, 47)]

    items = list_documents(db)

    assert len(items) == 1
    assert items[0].id == document_id
    assert items[0].filename == "training_manual.pdf"
    assert items[0].chunk_count == 47
    assert items[0].size_bytes == 2380 * 1024
    assert items[0].uploaded_at == uploaded_at


def test_get_document_returns_row() -> None:
    from rag_core.services.document_service import get_document

    db = MagicMock()
    document_id = uuid.uuid4()
    document = Document(filename="x.pdf", status=DocumentStatus.READY.value)
    document.id = document_id
    db.get.return_value = document
    assert get_document(db, document_id) is document


def test_count_chunks_for_document() -> None:
    from rag_core.services.document_service import count_chunks_for_document

    db = MagicMock()
    db.scalar.return_value = 5
    assert count_chunks_for_document(db, uuid.uuid4()) == 5
    db.scalar.return_value = None
    assert count_chunks_for_document(db, uuid.uuid4()) == 0


def test_list_ready_document_filenames_empty_limit() -> None:
    from rag_core.services.document_service import list_ready_document_filenames

    assert list_ready_document_filenames(MagicMock(), limit=0) == []


def test_list_ready_document_filenames() -> None:
    from rag_core.services.document_service import list_ready_document_filenames

    db = MagicMock()
    db.scalars.return_value.all.return_value = ["a.pdf", "b.pdf"]
    assert list_ready_document_filenames(db, limit=10) == ["a.pdf", "b.pdf"]


def test_sample_ready_document_snippets_empty_limit() -> None:
    from rag_core.services.document_service import sample_ready_document_snippets

    assert sample_ready_document_snippets(MagicMock(), limit=0) == []


def test_sample_ready_document_snippets_truncates_and_skips() -> None:
    from rag_core.services.document_service import sample_ready_document_snippets

    db = MagicMock()
    doc_ok = Document(filename="ok.pdf", status=DocumentStatus.READY.value)
    doc_ok.id = uuid.uuid4()
    doc_empty = Document(filename="empty.pdf", status=DocumentStatus.READY.value)
    doc_empty.id = uuid.uuid4()
    doc_none = Document(filename="none.pdf", status=DocumentStatus.READY.value)
    doc_none.id = uuid.uuid4()

    chunk_long = MagicMock()
    chunk_long.content = "word " * 200
    chunk_long.page_number = 2
    chunk_blank = MagicMock()
    chunk_blank.content = "   \n\t  "

    docs_result = MagicMock()
    docs_result.all.return_value = [doc_ok, doc_empty, doc_none]
    long_result = MagicMock()
    long_result.first.return_value = chunk_long
    blank_result = MagicMock()
    blank_result.first.return_value = chunk_blank
    none_result = MagicMock()
    none_result.first.return_value = None
    db.scalars.side_effect = [docs_result, long_result, blank_result, none_result]

    snippets = sample_ready_document_snippets(db, limit=8, max_chars=40)
    assert len(snippets) == 1
    assert snippets[0].filename == "ok.pdf"
    assert snippets[0].content.endswith("…")
    assert len(snippets[0].content) <= 40
    assert snippets[0].page_number == 2


def test_insert_chunks_empty_returns_zero() -> None:
    assert insert_chunks(MagicMock(), uuid.uuid4(), []) == 0
