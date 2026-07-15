"""Tests for Chainlit turn helpers."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.turn import ensure_thread, history_for_query, persist_turn_usage
from rag_core.core.token_usage import TokenUsage
from rag_core.rag.generation import RagStreamCapture
from rag_core.rag.schemas import ChatTurn


@pytest.fixture
def mock_db():
    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None
    return db, cm


def test_history_for_query_pairs_user_assistant(mock_db) -> None:
    db, cm = mock_db
    thread_id = uuid.uuid4()
    user = MagicMock(role="user", content="What is CHW?")
    assistant = MagicMock(role="assistant", content="Community health worker.")
    with patch("app.turn.get_session", return_value=cm):
        with patch("app.turn.chat_service.list_messages", return_value=[user, assistant]):
            history = history_for_query(thread_id)

    assert history == [
        ChatTurn(input="What is CHW?", response="Community health worker.")
    ]


def test_history_for_query_none_thread() -> None:
    assert history_for_query(None) == []


def test_ensure_thread_creates_and_persists_user(mock_db) -> None:
    db, cm = mock_db
    thread_id = uuid.uuid4()
    thread = MagicMock()
    thread.id = thread_id
    thread.title = "What is malaria?"

    with patch("app.turn.get_session", return_value=cm):
        with patch("app.turn.chat_service.get_thread", return_value=None):
            with patch(
                "app.turn.chat_service.derive_thread_title",
                return_value="What is malaria?",
            ):
                with patch("app.turn.chat_service.add_message") as add_msg:
                    with patch("app.turn.ChatThread") as thread_cls:
                        thread_cls.return_value = thread
                        result_id, title = ensure_thread(
                            "What is malaria?",
                            thread_id=thread_id,
                        )

    assert result_id == thread_id
    assert title == "What is malaria?"
    add_msg.assert_called_once()
    assert add_msg.call_args.kwargs["role"] == "user"
    db.commit.assert_called_once()


def test_ensure_thread_rejects_blank() -> None:
    with pytest.raises(ValueError, match="blank"):
        ensure_thread("   ")


def test_persist_turn_usage_records_embed_and_completion(mock_db) -> None:
    db, cm = mock_db
    thread_id = uuid.uuid4()
    thread = MagicMock()
    thread.id = thread_id
    user_msg = MagicMock()
    user_msg.id = uuid.uuid4()
    assistant_msg = MagicMock()
    assistant_msg.id = uuid.uuid4()

    capture = RagStreamCapture()
    capture.query_embed_usage = TokenUsage(
        prompt_tokens=4,
        model="text-embedding-3-small",
        is_embedding=True,
    )
    capture.completion_usage = TokenUsage(
        prompt_tokens=100,
        completion_tokens=50,
        model="gpt-4o-mini",
    )

    with patch("app.turn.get_session", return_value=cm):
        with patch("app.turn.chat_service.get_thread", return_value=thread):
            with patch(
                "app.turn.chat_service.get_latest_user_message",
                return_value=user_msg,
            ):
                with patch(
                    "app.turn.chat_service.add_message",
                    return_value=assistant_msg,
                ) as add_msg:
                    with patch("app.turn.apply_usage_to_message") as apply_msg:
                        with patch("app.turn.record_usage_event") as record:
                            persist_turn_usage(
                                thread_id,
                                assistant_content="Grounded answer",
                                capture=capture,
                            )

    apply_msg.assert_called_once()
    assert record.call_count == 2
    add_msg.assert_called_once()
    assert add_msg.call_args.kwargs["role"] == "assistant"
    db.commit.assert_called_once()
