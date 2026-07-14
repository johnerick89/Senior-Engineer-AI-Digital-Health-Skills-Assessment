"""Tests for POST /chat validation and RAG streaming."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

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


def test_chat_rejects_blank_input(client: TestClient) -> None:
    response = client.post("/chat", json={"input": "  ", "history": []})
    assert response.status_code == 422


def test_chat_rejects_oversized_history(client: TestClient) -> None:
    history = [{"input": f"q{i}", "response": f"a{i}"} for i in range(21)]
    response = client.post(
        "/chat",
        json={"input": "hello", "history": history},
    )
    assert response.status_code == 422


@patch("app.chat.routes.stream_rag_answer")
def test_chat_streams_rag_answer(
    mock_stream: AsyncMock,
    client: TestClient,
) -> None:
    async def fake_stream(_query):
        yield "Grounded "
        yield "answer"

    mock_stream.side_effect = fake_stream

    response = client.post(
        "/chat",
        json={"input": "What is CHW?", "history": []},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text == "Grounded answer"
    mock_stream.assert_called_once()
