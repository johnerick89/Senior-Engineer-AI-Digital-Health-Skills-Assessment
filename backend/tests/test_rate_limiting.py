"""Tests for backend rate limiting on expensive endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient


@patch("app.api.chats.stream_rag_answer")
@patch("app.api.chats.persist_turn_usage")
@patch("app.api.chats.ensure_thread")
def test_chat_rate_limited_after_limit(
    mock_ensure: MagicMock,
    _mock_save: MagicMock,
    mock_stream: AsyncMock,
    client: TestClient,
) -> None:
    thread_id = uuid.uuid4()
    mock_ensure.return_value = (thread_id, "Rate limited chat")

    async def fake_stream(_query, capture=None):
        yield "ok"

    mock_stream.side_effect = fake_stream

    for _ in range(20):
        response = client.post("/api/v1/chats", json={"input": "hello", "history": []})
        assert response.status_code == 200

    response = client.post("/api/v1/chats", json={"input": "hello", "history": []})
    assert response.status_code == 429
    assert "rate limit" in response.text.lower()


@patch("app.api.documents.ingest_one")
def test_documents_upload_rate_limited_after_limit(
    mock_ingest_one: MagicMock,
    client: TestClient,
) -> None:
    mock_ingest_one.return_value = MagicMock(
        document_id="33333333-3333-3333-3333-333333333333",
        chunk_count=1,
        model_dump_json=lambda: (
            '{"filename":"guide.pdf","document_id":"33333333-3333-3333-3333-333333333333",'
            '"status":"ready","chunk_count":1,"error":null}'
        ),
    )

    files = [("files", ("guide.pdf", b"%PDF-1.4", "application/pdf"))]
    for _ in range(10):
        response = client.post("/api/v1/documents", files=files)
        assert response.status_code == 200

    response = client.post("/api/v1/documents", files=files)
    assert response.status_code == 429
    assert "rate limit" in response.text.lower()
