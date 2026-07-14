"""Tests for rag_core.services.chat_service."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from rag_core.models.chat_message import ChatMessage
from rag_core.models.chat_thread import ChatThread
from rag_core.services.chat_service import (
    add_message,
    create_thread,
    derive_thread_title,
    title_from_input,
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
