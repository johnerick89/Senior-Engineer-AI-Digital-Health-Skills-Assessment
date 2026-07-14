"""Chat thread and message persistence via SQLAlchemy ORM."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from rag_core.models.chat_message import ChatMessage
from rag_core.models.chat_thread import ChatThread

_TITLE_MAX_LEN = 72
_GREETING_TITLES = frozenset(
    {
        "hi",
        "hello",
        "hey",
        "hiya",
        "howdy",
        "thanks",
        "thank you",
        "thx",
        "good morning",
        "good afternoon",
        "good evening",
        "new chat",
    }
)


@dataclass(frozen=True)
class ThreadSummary:
    """Sidebar-friendly thread row."""

    id: uuid.UUID
    title: str | None
    updated_at: object | None


def _squash(text: str) -> str:
    return " ".join(text.split()).strip()


def title_from_input(user_input: str) -> str:
    """Build a short sidebar title from a user message."""
    cleaned = _squash(user_input)
    if not cleaned:
        return "New chat"
    if len(cleaned) <= _TITLE_MAX_LEN:
        return cleaned
    return cleaned[: _TITLE_MAX_LEN - 1].rstrip() + "…"


def derive_thread_title(
    user_input: str,
    *,
    existing_title: str | None,
    user_message_count_before: int,
) -> str:
    """Choose a title for the thread, refreshing when the prior one is weak.

    - First user message always sets the title.
    - Later messages keep the title unless it looks like a greeting / placeholder
      and the new input is more substantive.
    """
    candidate = title_from_input(user_input)
    if user_message_count_before <= 0 or not existing_title:
        return candidate

    prior = _squash(existing_title).lower().rstrip(".!?")
    if prior in _GREETING_TITLES and candidate.lower().rstrip(".!?") not in _GREETING_TITLES:
        return candidate
    return existing_title


def create_thread(db: Session, *, title: str | None = None) -> ChatThread:
    """Insert a chat_threads row and return it (flushed, not committed)."""
    thread = ChatThread(title=title)
    db.add(thread)
    db.flush()
    return thread


def get_thread(db: Session, thread_id: uuid.UUID) -> ChatThread | None:
    """Return a thread by id, or None."""
    return db.get(ChatThread, thread_id)


def count_user_messages(db: Session, thread_id: uuid.UUID) -> int:
    """Count user-role messages on a thread."""
    stmt = (
        select(ChatMessage.id)
        .where(ChatMessage.thread_id == thread_id)
        .where(ChatMessage.role == "user")
    )
    return len(db.scalars(stmt).all())


def update_thread_title(db: Session, thread: ChatThread, title: str) -> ChatThread:
    """Set thread.title and flush."""
    thread.title = title
    db.flush()
    return thread


def add_message(
    db: Session,
    thread_id: uuid.UUID,
    *,
    role: str,
    content: str,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    total_tokens: int | None = None,
    estimated_cost_usd: object | None = None,
    model: str | None = None,
) -> ChatMessage:
    """Insert a chat_messages row (flushed, not committed)."""
    if role not in ("user", "assistant"):
        raise ValueError("role must be 'user' or 'assistant'")
    text = content.strip()
    if not text:
        raise ValueError("content must not be blank")
    message = ChatMessage(
        thread_id=thread_id,
        role=role,
        content=text,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost_usd=estimated_cost_usd,
        model=model,
    )
    db.add(message)
    db.flush()
    return message


def list_threads(db: Session, *, limit: int = 50) -> list[ChatThread]:
    """Return recent threads ordered by updated_at descending."""
    stmt = (
        select(ChatThread)
        .order_by(ChatThread.updated_at.desc().nullslast(), ChatThread.created_at.desc())
        .limit(max(1, limit))
    )
    return list(db.scalars(stmt).all())


def list_messages(db: Session, thread_id: uuid.UUID) -> list[ChatMessage]:
    """Return messages for a thread in chronological order."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    return list(db.scalars(stmt).all())


def get_latest_user_message(db: Session, thread_id: uuid.UUID) -> ChatMessage | None:
    """Return the most recent user message on a thread, if any."""
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.thread_id == thread_id)
        .where(ChatMessage.role == "user")
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(1)
    )
    return db.scalars(stmt).first()
