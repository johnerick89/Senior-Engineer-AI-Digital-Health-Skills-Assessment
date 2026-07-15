"""Tests for /api/v1/chats validation, streams, threads, messages, and usage."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

CHATS_URL = "/api/v1/chats"


def test_legacy_chat_path_is_gone(client: TestClient) -> None:
    response = client.post("/chat", json={"input": "hello", "history": []})
    assert response.status_code == 404


def test_chat_rejects_blank_input(client: TestClient) -> None:
    response = client.post(CHATS_URL, json={"input": "  ", "history": []})
    assert response.status_code == 422


def test_chat_rejects_oversized_history(client: TestClient) -> None:
    history = [{"input": f"q{i}", "response": f"a{i}"} for i in range(21)]
    response = client.post(
        CHATS_URL,
        json={"input": "hello", "history": history},
    )
    assert response.status_code == 422


def test_chat_rejects_blank_history_turn(client: TestClient) -> None:
    response = client.post(
        CHATS_URL,
        json={
            "input": "follow up",
            "history": [{"input": "  ", "response": "answer"}],
        },
    )
    assert response.status_code == 422


@patch("app.api.chats.stream_rag_answer")
@patch("app.api.chats.persist_turn_usage")
@patch("app.api.chats.ensure_thread")
def test_chat_streams_rag_answer_with_thread_headers(
    mock_ensure: MagicMock,
    mock_save: MagicMock,
    mock_stream: AsyncMock,
    client: TestClient,
) -> None:
    thread_id = uuid.uuid4()
    mock_ensure.return_value = (thread_id, "What is CHW?")

    async def fake_stream(_query, capture=None):
        yield "Grounded "
        yield "answer"

    mock_stream.side_effect = fake_stream

    response = client.post(
        CHATS_URL,
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
    assert mock_save.call_args.kwargs["assistant_content"] == "Grounded answer"


@patch("app.api.chats.stream_rag_answer")
@patch("app.api.chats.persist_turn_usage")
@patch("app.api.chats.ensure_thread")
def test_chat_passes_existing_thread_id_to_ensure(
    mock_ensure: MagicMock,
    mock_save: MagicMock,
    mock_stream: AsyncMock,
    client: TestClient,
) -> None:
    thread_id = uuid.uuid4()
    mock_ensure.return_value = (thread_id, "Follow-up")

    async def fake_stream(_query, capture=None):
        yield "ok"

    mock_stream.side_effect = fake_stream

    response = client.post(
        CHATS_URL,
        json={"input": "more", "history": [], "id": str(thread_id)},
    )
    assert response.status_code == 200
    request_arg = mock_ensure.call_args.args[0]
    assert request_arg.id == thread_id
    mock_save.assert_called_once()


@patch("app.api.chats.ensure_thread", side_effect=LookupError("missing"))
def test_chat_unknown_thread_returns_404(
    _mock_ensure: MagicMock,
    client: TestClient,
) -> None:
    response = client.post(
        CHATS_URL,
        json={
            "input": "hello",
            "history": [],
            "id": str(uuid.uuid4()),
        },
    )
    assert response.status_code == 404


@patch("app.api.chats.get_session")
@patch("app.api.chats.chat_service.list_threads")
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

    response = client.get(CHATS_URL)
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["title"] == "Saved chat"
    assert payload[0]["id"] == str(thread.id)


@patch(
    "app.api.chats.suggest_chat_topics",
    new_callable=AsyncMock,
    return_value=["What is ACT for malaria?", "Summarize CHW duties."],
)
def test_chat_suggestions(
    _mock_topics: AsyncMock,
    client: TestClient,
) -> None:
    response = client.get(f"{CHATS_URL}/suggestions")
    assert response.status_code == 200
    assert response.json() == {
        "topics": ["What is ACT for malaria?", "Summarize CHW duties."],
    }


@patch(
    "app.api.chats.suggest_chat_topics",
    new_callable=AsyncMock,
    return_value=[],
)
def test_chat_suggestions_empty(
    _mock_topics: AsyncMock,
    client: TestClient,
) -> None:
    response = client.get(f"{CHATS_URL}/suggestions")
    assert response.status_code == 200
    assert response.json() == {"topics": []}


@patch("app.api.chats.get_session")
@patch("app.api.chats.chat_service.list_messages")
@patch("app.api.chats.chat_service.get_thread")
def test_get_chat_messages(
    mock_get_thread: MagicMock,
    mock_list_messages: MagicMock,
    mock_get_session: MagicMock,
    client: TestClient,
) -> None:
    thread_id = uuid.uuid4()
    mock_get_thread.return_value = MagicMock(id=thread_id)
    msg = MagicMock()
    msg.id = uuid.uuid4()
    msg.role = "user"
    msg.content = "Hello"
    msg.created_at = None
    msg.prompt_tokens = 4
    msg.completion_tokens = 0
    msg.total_tokens = 4
    msg.estimated_cost_usd = Decimal("0.000001")
    msg.model = "text-embedding-3-small"
    mock_list_messages.return_value = [msg]
    cm = MagicMock()
    cm.__enter__.return_value = MagicMock()
    cm.__exit__.return_value = None
    mock_get_session.return_value = cm

    response = client.get(f"{CHATS_URL}/{thread_id}/messages")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["role"] == "user"
    assert payload[0]["content"] == "Hello"
    assert payload[0]["prompt_tokens"] == 4
    assert payload[0]["model"] == "text-embedding-3-small"


@patch("app.api.chats.get_session")
@patch("app.api.chats.chat_service.get_thread", return_value=None)
def test_get_chat_messages_404(
    _mock_get_thread: MagicMock,
    mock_get_session: MagicMock,
    client: TestClient,
) -> None:
    cm = MagicMock()
    cm.__enter__.return_value = MagicMock()
    cm.__exit__.return_value = None
    mock_get_session.return_value = cm

    response = client.get(f"{CHATS_URL}/{uuid.uuid4()}/messages")
    assert response.status_code == 404


def test_get_chat_messages_invalid_uuid(client: TestClient) -> None:
    response = client.get(f"{CHATS_URL}/not-a-uuid/messages")
    assert response.status_code == 422


@patch("app.api.chats.get_session")
@patch("app.api.chats.summarize_thread_usage")
@patch("app.api.chats.chat_service.get_thread")
def test_get_chat_usage(
    mock_get_thread: MagicMock,
    mock_summarize: MagicMock,
    mock_get_session: MagicMock,
    client: TestClient,
) -> None:
    thread_id = uuid.uuid4()
    mock_get_thread.return_value = MagicMock(id=thread_id)
    mock_summarize.return_value = MagicMock(
        prompt_tokens=10,
        completion_tokens=20,
        total_tokens=30,
        estimated_cost_usd=0.00123456789,
    )
    cm = MagicMock()
    cm.__enter__.return_value = MagicMock()
    cm.__exit__.return_value = None
    mock_get_session.return_value = cm

    response = client.get(f"{CHATS_URL}/{thread_id}/usage")
    assert response.status_code == 200
    payload = response.json()
    assert payload["thread_id"] == str(thread_id)
    assert payload["prompt_tokens"] == 10
    assert payload["completion_tokens"] == 20
    assert payload["total_tokens"] == 30
    assert payload["estimated_cost_usd"] == 0.00123457


@patch("app.api.chats.get_session")
@patch("app.api.chats.chat_service.get_thread", return_value=None)
def test_get_chat_usage_404(
    _mock_get_thread: MagicMock,
    mock_get_session: MagicMock,
    client: TestClient,
) -> None:
    cm = MagicMock()
    cm.__enter__.return_value = MagicMock()
    cm.__exit__.return_value = None
    mock_get_session.return_value = cm

    response = client.get(f"{CHATS_URL}/{uuid.uuid4()}/usage")
    assert response.status_code == 404


@patch("app.api.usage.get_session")
@patch("app.api.usage.summarize_app_usage")
def test_usage_summary(
    mock_summarize: MagicMock,
    mock_get_session: MagicMock,
    client: TestClient,
) -> None:
    bucket = MagicMock(
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        estimated_cost_usd=0.5,
    )
    mock_summarize.return_value = MagicMock(
        chats=bucket,
        suggestions=bucket,
        embeddings=bucket,
        total_tokens=9,
        estimated_cost_usd=1.5,
    )
    cm = MagicMock()
    cm.__enter__.return_value = MagicMock()
    cm.__exit__.return_value = None
    mock_get_session.return_value = cm

    response = client.get("/api/v1/usage")
    assert response.status_code == 200
    payload = response.json()
    assert payload["total_tokens"] == 9
    assert payload["estimated_cost_usd"] == 1.5
    assert payload["chats"]["total_tokens"] == 3
    assert payload["suggestions"]["prompt_tokens"] == 1
    assert payload["embeddings"]["completion_tokens"] == 2


def test_legacy_usage_summary_path_is_gone(client: TestClient) -> None:
    response = client.get("/usage/summary")
    assert response.status_code == 404
