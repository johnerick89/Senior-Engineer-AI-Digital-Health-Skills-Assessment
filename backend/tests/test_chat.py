"""Tests for POST /chat validation, persistence headers, and thread listing."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

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
@patch("app.chat.routes._save_assistant_message")
@patch("app.chat.routes._ensure_thread")
def test_chat_streams_rag_answer_with_thread_headers(
    mock_ensure: MagicMock,
    mock_save: MagicMock,
    mock_stream: AsyncMock,
    client: TestClient,
) -> None:
    thread_id = uuid.uuid4()
    mock_ensure.return_value = (thread_id, "What is CHW?")

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
    assert response.headers["X-Chat-Id"] == str(thread_id)
    assert response.headers["X-Chat-Title"] == "What%20is%20CHW%3F"
    assert response.text == "Grounded answer"
    mock_stream.assert_called_once()
    mock_save.assert_called_once()
    assert mock_save.call_args.args[0] == thread_id
    assert mock_save.call_args.args[1] == "Grounded answer"


@patch("app.chat.routes._ensure_thread", side_effect=LookupError("missing"))
def test_chat_unknown_thread_returns_404(
    _mock_ensure: MagicMock,
    client: TestClient,
) -> None:
    response = client.post(
        "/chat",
        json={
            "input": "hello",
            "history": [],
            "id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404


@patch("app.chat.routes.get_session")
@patch("app.chat.routes.chat_service.list_threads")
def test_list_chats(
    mock_list: MagicMock,
    mock_get_session: MagicMock,
    client: TestClient,
) -> None:
    thread = MagicMock()
    thread.id = uuid.uuid4()
    thread.title = "Saved chat"
    thread.updated_at = None
    thread.created_at = None
    mock_list.return_value = [thread]
    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None
    mock_get_session.return_value = cm

    response = client.get("/chats")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Saved chat"
    assert payload[0]["id"] == str(thread.id)


@patch(
    "app.chat.routes.suggest_chat_topics",
    new_callable=AsyncMock,
    return_value=["What is ACT for malaria?", "Summarize CHW duties."],
)
def test_chat_suggestions(
    _mock_topics: AsyncMock,
    client: TestClient,
) -> None:
    response = client.get("/chat/suggestions")
    assert response.status_code == 200
    assert response.json() == {
        "topics": ["What is ACT for malaria?", "Summarize CHW duties."],
    }
