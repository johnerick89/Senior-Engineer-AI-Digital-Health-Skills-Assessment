"""Tests for rag_core.services.chat_service."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from rag_core.models.chat_message import ChatMessage
from rag_core.models.chat_thread import ChatThread
from rag_core.services.chat_service import (
    add_message,
    count_user_messages,
    create_thread,
    derive_thread_title,
    get_latest_user_message,
    get_thread,
    list_messages,
    list_threads,
    title_from_input,
    update_thread_title,
)


def test_title_from_input_truncates() -> None:
    long = "a" * 100
    title = title_from_input(long)
    assert title.endswith("…")
    assert len(title) == 72


def test_derive_title_first_message() -> None:
    assert derive_thread_title(
        "Malaria dosing",
        existing_title=None,
        user_message_count_before=0,
    ) == "Malaria dosing"


def test_derive_title_upgrades_greeting() -> None:
    title = derive_thread_title(
        "Tell me about Joshua",
        existing_title="Hello",
        user_message_count_before=1,
    )
    assert title == "Tell me about Joshua"


def test_derive_title_keeps_solid_existing() -> None:
    title = derive_thread_title(
        "follow up",
        existing_title="Community health protocols",
        user_message_count_before=2,
    )
    assert title == "Community health protocols"


def test_create_thread_adds_and_flushes() -> None:
    db = MagicMock()
    thread = create_thread(db, title="Hello")
    assert isinstance(thread, ChatThread)
    assert thread.title == "Hello"
    db.add.assert_called_once_with(thread)
    db.flush.assert_called_once()


def test_add_message_adds_orm_row() -> None:
    db = MagicMock()
    thread_id = uuid.uuid4()
    message = add_message(db, thread_id, role="user", content=" hi ")
    assert isinstance(message, ChatMessage)
    assert message.role == "user"
    assert message.content == "hi"
    assert message.thread_id == thread_id
    db.add.assert_called_once_with(message)


def test_title_from_input_blank_is_new_chat() -> None:
    assert title_from_input("   ") == "New chat"


def test_get_thread_and_update_title() -> None:
    db = MagicMock()
    thread_id = uuid.uuid4()
    thread = ChatThread(title="Hi")
    thread.id = thread_id
    db.get.return_value = thread
    assert get_thread(db, thread_id) is thread
    updated = update_thread_title(db, thread, "Substantive title")
    assert updated.title == "Substantive title"
    db.flush.assert_called()


def test_count_user_messages() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = [1, 2, 3]
    assert count_user_messages(db, uuid.uuid4()) == 3


def test_add_message_rejects_bad_role_and_blank() -> None:
    with pytest.raises(ValueError, match="role"):
        add_message(MagicMock(), uuid.uuid4(), role="system", content="x")
    with pytest.raises(ValueError, match="blank"):
        add_message(MagicMock(), uuid.uuid4(), role="user", content="  ")


def test_list_threads_and_messages_and_latest_user() -> None:
    thread = ChatThread(title="t")
    msg = ChatMessage(thread_id=uuid.uuid4(), role="user", content="hi")

    db_threads = MagicMock()
    db_threads.scalars.return_value.all.return_value = [thread]
    assert list_threads(db_threads, limit=10) == [thread]

    db_messages = MagicMock()
    db_messages.scalars.return_value.all.return_value = [msg]
    assert list_messages(db_messages, uuid.uuid4()) == [msg]

    db_latest = MagicMock()
    db_latest.scalars.return_value.first.return_value = msg
    assert get_latest_user_message(db_latest, uuid.uuid4()) is msg
