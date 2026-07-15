"""Tests for /api/v1/documents validation, streaming, list, and delete."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.schemas.documents import DocumentOut
from app.services.documents import MAX_FILE_SIZE_BYTES

DOCUMENTS_URL = "/api/v1/documents"


def test_legacy_upload_path_is_gone(client: TestClient) -> None:
    response = client.post("/upload")
    assert response.status_code == 404


def test_upload_rejects_empty_batch(client: TestClient) -> None:
    response = client.post(DOCUMENTS_URL)
    assert response.status_code == 400
    assert "At least one" in response.json()["detail"]


def test_upload_rejects_non_pdf(client: TestClient) -> None:
    response = client.post(
        DOCUMENTS_URL,
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_rejects_empty_file(client: TestClient) -> None:
    response = client.post(
        DOCUMENTS_URL,
        files=[("files", ("empty.pdf", b"", "application/pdf"))],
    )
    assert response.status_code == 400
    assert "empty" in response.json()["detail"].lower()


def test_upload_rejects_oversized_file(client: TestClient) -> None:
    too_big = b"x" * (MAX_FILE_SIZE_BYTES + 1)
    response = client.post(
        DOCUMENTS_URL,
        files=[("files", ("huge.pdf", too_big, "application/pdf"))],
    )
    assert response.status_code == 400
    assert "20MB" in response.json()["detail"]


def test_upload_rejects_invalid_before_any_ingest(client: TestClient) -> None:
    with patch("app.services.documents.ingest_pdf") as mock_ingest:
        response = client.post(
            DOCUMENTS_URL,
            files=[
                ("files", ("ok.pdf", b"%PDF-ok", "application/pdf")),
                ("files", ("bad.txt", b"nope", "text/plain")),
            ],
        )
    assert response.status_code == 400
    mock_ingest.assert_not_called()


@patch("app.services.documents.ingest_pdf")
def test_upload_streams_ready_ndjson(
    mock_ingest: MagicMock,
    client: TestClient,
) -> None:
    mock_result = MagicMock()
    mock_result.document_id = "11111111-1111-1111-1111-111111111111"
    mock_result.chunk_count = 3
    mock_ingest.return_value = mock_result

    response = client.post(
        DOCUMENTS_URL,
        files=[("files", ("guide.pdf", b"%PDF-1.4 fake", "application/pdf"))],
    )

    assert response.status_code == 200
    assert "ndjson" in response.headers["content-type"]
    lines = [line for line in response.text.strip().split("\n") if line]
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["filename"] == "guide.pdf"
    assert payload["status"] == "ready"
    assert payload["chunk_count"] == 3
    assert payload["document_id"] == "11111111-1111-1111-1111-111111111111"


@patch("app.services.documents.ingest_pdf")
def test_upload_appends_pdf_extension_from_content_type(
    mock_ingest: MagicMock,
    client: TestClient,
) -> None:
    mock_result = MagicMock()
    mock_result.document_id = "22222222-2222-2222-2222-222222222222"
    mock_result.chunk_count = 1
    mock_ingest.return_value = mock_result

    response = client.post(
        DOCUMENTS_URL,
        files=[("files", ("guide", b"%PDF-1.4", "application/pdf"))],
    )
    assert response.status_code == 200
    payload = json.loads(response.text.strip().split("\n")[0])
    assert payload["filename"] == "guide.pdf"
    assert mock_ingest.call_args.kwargs["filename"] == "guide.pdf"


@patch("app.services.documents.ingest_pdf", side_effect=RuntimeError("embed down"))
def test_upload_streams_failed_and_continues(
    _mock_ingest: MagicMock,
    client: TestClient,
) -> None:
    response = client.post(
        DOCUMENTS_URL,
        files=[
            ("files", ("a.pdf", b"%PDF-a", "application/pdf")),
            ("files", ("b.pdf", b"%PDF-b", "application/pdf")),
        ],
    )

    assert response.status_code == 200
    lines = [json.loads(line) for line in response.text.strip().split("\n") if line]
    assert len(lines) == 2
    assert all(item["status"] == "failed" for item in lines)
    assert "embed down" in lines[0]["error"]


@patch("app.services.documents.ingest_pdf")
def test_upload_mixed_ready_and_failed(
    mock_ingest: MagicMock,
    client: TestClient,
) -> None:
    ready = MagicMock()
    ready.document_id = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    ready.chunk_count = 2
    mock_ingest.side_effect = [ready, RuntimeError("boom")]

    response = client.post(
        DOCUMENTS_URL,
        files=[
            ("files", ("a.pdf", b"%PDF-a", "application/pdf")),
            ("files", ("b.pdf", b"%PDF-b", "application/pdf")),
        ],
    )
    assert response.status_code == 200
    lines = [json.loads(line) for line in response.text.strip().split("\n") if line]
    assert lines[0]["status"] == "ready"
    assert lines[1]["status"] == "failed"
    assert "boom" in lines[1]["error"]


@patch("app.api.documents.list_documents", return_value=[])
def test_list_documents_empty(
    _mock_list: MagicMock,
    client: TestClient,
) -> None:
    response = client.get(DOCUMENTS_URL)
    assert response.status_code == 200
    assert response.json() == []


@patch("app.api.documents.list_documents")
def test_list_documents_populated(
    mock_list: MagicMock,
    client: TestClient,
) -> None:
    doc_id = uuid.uuid4()
    mock_list.return_value = [
        DocumentOut(
            id=doc_id,
            filename="training_manual.pdf",
            status="ready",
            size_kb=2380,
            chunk_count=47,
            uploaded_at=datetime(2026, 7, 13, 10, 22, tzinfo=timezone.utc),
            error_message=None,
        )
    ]

    response = client.get(DOCUMENTS_URL)
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["id"] == str(doc_id)
    assert payload[0]["filename"] == "training_manual.pdf"
    assert payload[0]["status"] == "ready"
    assert payload[0]["size_kb"] == 2380
    assert payload[0]["chunk_count"] == 47
    assert payload[0]["error_message"] is None


@patch("app.api.documents.delete_document", return_value=True)
def test_delete_document_returns_204(
    mock_delete: MagicMock,
    client: TestClient,
) -> None:
    doc_id = uuid.uuid4()
    response = client.delete(f"{DOCUMENTS_URL}/{doc_id}")
    assert response.status_code == 204
    assert response.content == b""
    mock_delete.assert_called_once_with(doc_id)


@patch("app.api.documents.delete_document", return_value=False)
def test_delete_document_returns_404(
    _mock_delete: MagicMock,
    client: TestClient,
) -> None:
    response = client.delete(f"{DOCUMENTS_URL}/{uuid.uuid4()}")
    assert response.status_code == 404
    assert response.json()["detail"] == "Document not found"


@patch("app.services.documents.document_service.delete_document", return_value=True)
@patch("app.services.documents.get_session")
def test_delete_document_service_commits(
    mock_get_session: MagicMock,
    mock_delete: MagicMock,
) -> None:
    """HTTP delete path commits after rag_core delete (CASCADE owned by DB)."""
    from app.services.documents import delete_document

    doc_id = uuid.uuid4()
    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None
    mock_get_session.return_value = cm

    assert delete_document(doc_id) is True
    mock_delete.assert_called_once_with(db, doc_id)
    db.commit.assert_called_once()
