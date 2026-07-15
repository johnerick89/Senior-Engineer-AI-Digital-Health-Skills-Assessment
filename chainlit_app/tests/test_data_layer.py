"""Tests for the rag_core-backed Chainlit data layer."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from chainlit.types import Pagination, ThreadFilter

from app.data_layer import ANONYMOUS_USER_ID, RagCoreDataLayer


@pytest.mark.asyncio
async def test_list_threads_maps_rows() -> None:
    layer = RagCoreDataLayer()
    thread = MagicMock()
    thread.id = uuid.uuid4()
    thread.title = "Saved chat"
    thread.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    thread.updated_at = thread.created_at

    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None

    with patch("app.data_layer.get_session", return_value=cm):
        with patch("app.data_layer.chat_service.list_threads", return_value=[thread]):
            result = await layer.list_threads(
                Pagination(first=20, cursor=None),
                ThreadFilter(userId=ANONYMOUS_USER_ID),
            )

    assert len(result.data) == 1
    assert result.data[0]["id"] == str(thread.id)
    assert result.data[0]["name"] == "Saved chat"
    assert result.data[0]["userId"] == ANONYMOUS_USER_ID
    assert result.pageInfo.hasNextPage is False


@pytest.mark.asyncio
async def test_get_thread_includes_steps() -> None:
    layer = RagCoreDataLayer()
    thread_id = uuid.uuid4()
    thread = MagicMock()
    thread.id = thread_id
    thread.title = "CHW"
    thread.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    user = MagicMock()
    user.id = uuid.uuid4()
    user.role = "user"
    user.content = "Hello"
    user.created_at = thread.created_at

    db = MagicMock()
    cm = MagicMock()
    cm.__enter__.return_value = db
    cm.__exit__.return_value = None

    with patch("app.data_layer.get_session", return_value=cm):
        with patch("app.data_layer.chat_service.get_thread", return_value=thread):
            with patch(
                "app.data_layer.chat_service.list_messages",
                return_value=[user],
            ):
                result = await layer.get_thread(str(thread_id))

    assert result is not None
    assert result["id"] == str(thread_id)
    assert len(result["steps"]) == 1
    assert result["steps"][0]["type"] == "user_message"
