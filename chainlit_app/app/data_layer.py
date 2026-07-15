"""Chainlit data layer backed by rag_core chat_threads / chat_messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Dict, List, Optional

from chainlit.data.base import BaseDataLayer
from chainlit.types import (
    Feedback,
    PageInfo,
    PaginatedResponse,
    Pagination,
    ThreadDict,
    ThreadFilter,
)
from chainlit.user import PersistedUser, User

from rag_core.db.session import get_session
from rag_core.models.chat_thread import ChatThread
from rag_core.services import chat_service

if TYPE_CHECKING:
    from chainlit.element import Element, ElementDict
    from chainlit.step import StepDict

ANONYMOUS_USER_ID = "anonymous"
ANONYMOUS_CREATED_AT = "2020-01-01T00:00:00+00:00"


def _iso(dt: datetime | None) -> str:
    if dt is None:
        return datetime.now(timezone.utc).isoformat()
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc).isoformat()
    return dt.isoformat()


def _parse_uuid(value: str) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError):
        return None


def _message_to_step(message, thread_id: str) -> "StepDict":
    step_type = (
        "user_message" if message.role == "user" else "assistant_message"
    )
    created = _iso(message.created_at)
    content = message.content
    return {
        "id": str(message.id),
        "threadId": thread_id,
        "parentId": None,
        "name": "user" if message.role == "user" else "assistant",
        "type": step_type,
        "streaming": False,
        "waitForAnswer": False,
        "isError": False,
        "metadata": {},
        "tags": None,
        "input": content if message.role == "user" else "",
        "output": content if message.role == "assistant" else "",
        "createdAt": created,
        "start": created,
        "end": created,
        "generation": None,
        "showInput": True,
        "language": None,
        "feedback": None,
    }


def _thread_to_dict(
    thread: ChatThread,
    *,
    include_steps: bool = False,
) -> ThreadDict:
    thread_id = str(thread.id)
    steps: list = []
    if include_steps:
        with get_session() as db:
            messages = chat_service.list_messages(db, thread.id)
        steps = [_message_to_step(m, thread_id) for m in messages]

    return {
        "id": thread_id,
        "createdAt": _iso(thread.created_at),
        "name": thread.title or "New chat",
        "userId": ANONYMOUS_USER_ID,
        "userIdentifier": ANONYMOUS_USER_ID,
        "tags": [],
        "metadata": {},
        "steps": steps,
        "elements": [],
    }


class RagCoreDataLayer(BaseDataLayer):
    """Persist Chainlit history against shared rag_core chat tables."""

    async def get_user(self, identifier: str) -> Optional[PersistedUser]:
        return PersistedUser(
            id=ANONYMOUS_USER_ID,
            createdAt=ANONYMOUS_CREATED_AT,
            identifier=ANONYMOUS_USER_ID,
            display_name=identifier or "Guest",
            metadata={"provider": "credentials"},
        )

    async def create_user(self, user: User) -> Optional[PersistedUser]:
        return PersistedUser(
            id=ANONYMOUS_USER_ID,
            createdAt=ANONYMOUS_CREATED_AT,
            identifier=ANONYMOUS_USER_ID,
            display_name=user.identifier or "Guest",
            metadata=user.metadata or {"provider": "credentials"},
        )

    async def delete_feedback(self, feedback_id: str) -> bool:
        return True

    async def upsert_feedback(self, feedback: Feedback) -> str:
        return getattr(feedback, "id", None) or str(uuid.uuid4())

    async def create_element(self, element: "Element") -> None:
        return None

    async def get_element(
        self, thread_id: str, element_id: str
    ) -> Optional["ElementDict"]:
        return None

    async def delete_element(
        self, element_id: str, thread_id: Optional[str] = None
    ) -> None:
        return None

    async def create_step(self, step_dict: "StepDict") -> None:
        # Chat messages are written by app.turn (ensure_thread / persist_turn_usage).
        return None

    async def update_step(self, step_dict: "StepDict") -> None:
        return None

    async def delete_step(self, step_id: str) -> None:
        return None

    async def get_thread_author(self, thread_id: str) -> str:
        return ANONYMOUS_USER_ID

    async def delete_thread(self, thread_id: str) -> None:
        tid = _parse_uuid(thread_id)
        if tid is None:
            return
        with get_session() as db:
            thread = chat_service.get_thread(db, tid)
            if thread is not None:
                db.delete(thread)
                db.commit()

    async def list_threads(
        self, pagination: Pagination, filters: ThreadFilter
    ) -> PaginatedResponse[ThreadDict]:
        limit = max(1, int(pagination.first or 20))
        with get_session() as db:
            threads = chat_service.list_threads(db, limit=limit + 1)

        search = (filters.search or "").strip().lower() if filters else ""
        if search:
            threads = [
                t
                for t in threads
                if search in (t.title or "").lower()
            ]

        page = threads[:limit]
        has_next = len(threads) > limit
        data = [_thread_to_dict(t, include_steps=False) for t in page]
        start = data[0]["id"] if data else None
        end = data[-1]["id"] if data else None
        return PaginatedResponse(
            data=data,
            pageInfo=PageInfo(
                hasNextPage=has_next,
                startCursor=start,
                endCursor=end,
            ),
        )

    async def get_thread(self, thread_id: str) -> Optional[ThreadDict]:
        tid = _parse_uuid(thread_id)
        if tid is None:
            return None
        with get_session() as db:
            thread = chat_service.get_thread(db, tid)
            if thread is None:
                return None
            return _thread_to_dict(thread, include_steps=True)

    async def update_thread(
        self,
        thread_id: str,
        name: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict] = None,
        tags: Optional[List[str]] = None,
    ) -> None:
        tid = _parse_uuid(thread_id)
        if tid is None:
            return
        with get_session() as db:
            thread = chat_service.get_thread(db, tid)
            if thread is None:
                # Lazily register Chainlit's thread id so sidebar IDs match.
                thread = ChatThread(id=tid, title=name or "New chat")
                db.add(thread)
                db.flush()
            elif name and name != thread.title:
                chat_service.update_thread_title(db, thread, name)
            db.commit()

    async def build_debug_url(self) -> str:
        return ""

    async def close(self) -> None:
        return None

    async def get_favorite_steps(self, user_id: str) -> List["StepDict"]:
        return []
