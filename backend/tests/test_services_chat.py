"""Unit tests for app.services.chat helpers."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.schemas.chat import ChatRequest
from app.services.chat import bucket_out, ensure_thread, persist_turn_usage
from rag_core.core.token_usage import TokenUsage
from rag_core.rag.generation import RagStreamCapture


def test_bucket_out_rounds_cost() -> None:
    bucket = MagicMock(
        prompt_tokens=1,
        completion_tokens=2,
        total_tokens=3,
        estimated_cost_usd=0.123456789,
    )
    out = bucket_out(bucket)
    assert out.prompt_tokens == 1
    assert out.estimated_cost_usd == 0.12345679


def test_ensure_thread_creates_new() -> None:
    request = ChatRequest(input="What is CHW?", history=[])
    thread = MagicMock()
    thread.id = uuid.uuid4()
    thread.title = "What is CHW?"

    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None

    with patch("app.services.chat.get_session", return_value=cm):
        with patch(
            "app.services.chat.chat_service.derive_thread_title",
            return_value="What is CHW?",
        ):
            with patch(
                "app.services.chat.chat_service.create_thread",
                return_value=thread,
            ) as create:
                with patch("app.services.chat.chat_service.add_message") as add_msg:
                    thread_id, title = ensure_thread(request)

    assert thread_id == thread.id
    assert title == "What is CHW?"
    create.assert_called_once()
    add_msg.assert_called_once()
    assert add_msg.call_args.kwargs["role"] == "user"
    db.commit.assert_called_once()


def test_ensure_thread_missing_raises() -> None:
    request = ChatRequest(input="hello", history=[], id=uuid.uuid4())
    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None

    with patch("app.services.chat.get_session", return_value=cm):
        with patch("app.services.chat.chat_service.get_thread", return_value=None):
            with pytest.raises(LookupError):
                ensure_thread(request)


def test_ensure_thread_updates_existing_title() -> None:
    thread_id = uuid.uuid4()
    request = ChatRequest(input="Malaria protocol", history=[], id=thread_id)
    thread = MagicMock()
    thread.id = thread_id
    thread.title = "hi"

    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None

    with patch("app.services.chat.get_session", return_value=cm):
        with patch("app.services.chat.chat_service.get_thread", return_value=thread):
            with patch(
                "app.services.chat.chat_service.count_user_messages",
                return_value=1,
            ):
                with patch(
                    "app.services.chat.chat_service.derive_thread_title",
                    return_value="Malaria protocol",
                ):
                    with patch(
                        "app.services.chat.chat_service.update_thread_title",
                        side_effect=lambda db, t, new_title: setattr(t, "title", new_title),
                    ) as update:
                        with patch("app.services.chat.chat_service.add_message"):
                            result_id, title = ensure_thread(request)

    assert result_id == thread_id
    assert title == "Malaria protocol"
    update.assert_called_once()


def test_persist_turn_usage_records_embed_and_completion() -> None:
    thread_id = uuid.uuid4()
    thread = MagicMock(id=thread_id)
    user_msg = MagicMock(id=uuid.uuid4())
    assistant_msg = MagicMock(id=uuid.uuid4())
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

    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None

    with patch("app.services.chat.get_session", return_value=cm):
        with patch("app.services.chat.chat_service.get_thread", return_value=thread):
            with patch(
                "app.services.chat.chat_service.get_latest_user_message",
                return_value=user_msg,
            ):
                with patch(
                    "app.services.chat.chat_service.add_message",
                    return_value=assistant_msg,
                ) as add_msg:
                    with patch("app.services.chat.apply_usage_to_message") as apply_msg:
                        with patch("app.services.chat.record_usage_event") as record:
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


def test_persist_turn_usage_noop_when_thread_missing() -> None:
    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None

    with patch("app.services.chat.get_session", return_value=cm):
        with patch("app.services.chat.chat_service.get_thread", return_value=None):
            with patch("app.services.chat.chat_service.add_message") as add_msg:
                persist_turn_usage(
                    uuid.uuid4(),
                    assistant_content="x",
                    capture=RagStreamCapture(),
                )

    add_msg.assert_not_called()
    db.commit.assert_not_called()


def test_persist_turn_usage_skips_blank_assistant() -> None:
    thread_id = uuid.uuid4()
    thread = MagicMock(id=thread_id)
    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None

    with patch("app.services.chat.get_session", return_value=cm):
        with patch("app.services.chat.chat_service.get_thread", return_value=thread):
            with patch(
                "app.services.chat.chat_service.get_latest_user_message",
                return_value=None,
            ):
                with patch("app.services.chat.chat_service.add_message") as add_msg:
                    persist_turn_usage(
                        thread_id,
                        assistant_content="   ",
                        capture=RagStreamCapture(),
                    )

    add_msg.assert_not_called()
    db.commit.assert_called_once()
