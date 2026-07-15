"""Token/cost recording helpers for chats, embeddings, and suggestions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from rag_core.core.token_usage import (
    TokenUsage,
    apportion_integers,
    estimate_embed_tokens_from_texts,
    usage_from_openai_response,
)
from rag_core.models.usage_event import UsageEvent, UsageKind

__all__ = [
    "TokenUsage",
    "UsageBucket",
    "UsageSummary",
    "ThreadUsageSummary",
    "apportion_integers",
    "apply_usage_to_chunk",
    "apply_usage_to_message",
    "estimate_embed_tokens_from_texts",
    "record_usage_event",
    "summarize_app_usage",
    "summarize_thread_usage",
    "usage_from_openai_response",
]


def record_usage_event(
    db: Session,
    *,
    kind: UsageKind | str,
    usage: TokenUsage,
    thread_id: uuid.UUID | None = None,
    message_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    chunk_id: uuid.UUID | None = None,
) -> UsageEvent:
    """Insert a usage_events ledger row."""
    kind_value = kind.value if isinstance(kind, UsageKind) else kind
    event = UsageEvent(
        kind=kind_value,
        model=usage.model or None,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        total_tokens=usage.total_tokens,
        estimated_cost_usd=usage.estimated_cost_usd,
        thread_id=thread_id,
        message_id=message_id,
        document_id=document_id,
        chunk_id=chunk_id,
    )
    db.add(event)
    db.flush()
    return event


def apply_usage_to_message(message: Any, usage: TokenUsage) -> None:
    """Copy usage fields onto a chat_messages row."""
    message.prompt_tokens = usage.prompt_tokens
    message.completion_tokens = usage.completion_tokens
    message.total_tokens = usage.total_tokens
    message.estimated_cost_usd = usage.estimated_cost_usd
    message.model = usage.model or None


def apply_usage_to_chunk(
    chunk: Any,
    *,
    prompt_tokens: int,
    cost: Decimal,
    model: str,
) -> None:
    """Copy embedding usage onto a document_chunks row."""
    chunk.prompt_tokens = prompt_tokens
    chunk.estimated_cost_usd = cost
    chunk.model = model or None


@dataclass(frozen=True)
class ThreadUsageSummary:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


def summarize_thread_usage(db: Session, thread_id: uuid.UUID) -> ThreadUsageSummary:
    """Sum token/cost columns across messages in a thread."""
    from rag_core.models.chat_message import ChatMessage

    stmt = select(
        func.coalesce(func.sum(ChatMessage.prompt_tokens), 0),
        func.coalesce(func.sum(ChatMessage.completion_tokens), 0),
        func.coalesce(func.sum(ChatMessage.total_tokens), 0),
        func.coalesce(func.sum(ChatMessage.estimated_cost_usd), 0),
    ).where(ChatMessage.thread_id == thread_id)
    prompt, completion, total, cost = db.execute(stmt).one()
    return ThreadUsageSummary(
        prompt_tokens=int(prompt or 0),
        completion_tokens=int(completion or 0),
        total_tokens=int(total or 0),
        estimated_cost_usd=float(cost or 0),
    )


@dataclass(frozen=True)
class UsageBucket:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost_usd: float


@dataclass(frozen=True)
class UsageSummary:
    chats: UsageBucket
    suggestions: UsageBucket
    embeddings: UsageBucket
    total_tokens: int
    estimated_cost_usd: float


def _bucket_from_events(db: Session, kinds: list[str]) -> UsageBucket:
    stmt = select(
        func.coalesce(func.sum(UsageEvent.prompt_tokens), 0),
        func.coalesce(func.sum(UsageEvent.completion_tokens), 0),
        func.coalesce(func.sum(UsageEvent.total_tokens), 0),
        func.coalesce(func.sum(UsageEvent.estimated_cost_usd), 0),
    ).where(UsageEvent.kind.in_(kinds))
    prompt, completion, total, cost = db.execute(stmt).one()
    return UsageBucket(
        prompt_tokens=int(prompt or 0),
        completion_tokens=int(completion or 0),
        total_tokens=int(total or 0),
        estimated_cost_usd=float(cost or 0),
    )


def summarize_app_usage(db: Session) -> UsageSummary:
    """Roll up usage for the Usage sidebar."""
    chats = _bucket_from_events(
        db,
        [UsageKind.CHAT_COMPLETION.value, UsageKind.QUERY_EMBEDDING.value],
    )
    suggestions = _bucket_from_events(db, [UsageKind.SUGGESTION.value])
    embeddings = _bucket_from_events(db, [UsageKind.INGEST_EMBEDDING.value])
    total_tokens = chats.total_tokens + suggestions.total_tokens + embeddings.total_tokens
    total_cost = (
        chats.estimated_cost_usd
        + suggestions.estimated_cost_usd
        + embeddings.estimated_cost_usd
    )
    return UsageSummary(
        chats=chats,
        suggestions=suggestions,
        embeddings=embeddings,
        total_tokens=total_tokens,
        estimated_cost_usd=total_cost,
    )
