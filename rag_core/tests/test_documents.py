"""Tests for rag_core.services.document_service."""

import uuid
from unittest.mock import MagicMock

import pytest

from rag_core.models.document import Document, DocumentStatus
from rag_core.rag.embeddings import EMBEDDING_DIMENSION
from rag_core.services.document_service import (
    ChunkInsert,
    create_document,
    insert_chunks,
    update_document_status,
)


def _fake_embedding() -> list[float]:
    return [0.1] * EMBEDDING_DIMENSION


def test_create_document_adds_and_flushes() -> None:
    db = MagicMock()

    document = create_document(db, "guide.pdf")

    assert isinstance(document, Document)
    assert document.filename == "guide.pdf"
    assert document.status == DocumentStatus.PROCESSING.value
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
