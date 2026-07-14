"""Tests for POST /upload validation and streaming."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres",
    )
    with patch("rag_core.rag.vector_store.initialize_vector_store"):
        from app.main import app

        with TestClient(app) as test_client:
            yield test_client


def test_upload_rejects_empty_batch(client: TestClient) -> None:
    response = client.post("/upload")
    assert response.status_code == 400
    assert "At least one" in response.json()["detail"]


def test_upload_rejects_non_pdf(client: TestClient) -> None:
    response = client.post(
        "/upload",
        files=[("files", ("notes.txt", b"hello", "text/plain"))],
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


@patch("app.upload.routes.ingest_pdf")
def test_upload_streams_ready_ndjson(
    mock_ingest: MagicMock,
    client: TestClient,
) -> None:
    mock_result = MagicMock()
    mock_result.document_id = "11111111-1111-1111-1111-111111111111"
    mock_result.chunk_count = 3
    mock_ingest.return_value = mock_result

    response = client.post(
        "/upload",
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


@patch("app.upload.routes.ingest_pdf", side_effect=RuntimeError("embed down"))
def test_upload_streams_failed_and_continues(
    _mock_ingest: MagicMock,
    client: TestClient,
) -> None:
    response = client.post(
        "/upload",
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
