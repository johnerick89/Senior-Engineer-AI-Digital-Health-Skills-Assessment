"""UsageEvent ORM model — ledger for LLM/embedding cost events."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from rag_core.db.base import Base, UUIDPrimaryKeyMixin


class UsageKind(str, Enum):
    """Kinds of billable API calls we record."""

    SUGGESTION = "suggestion"
    CHAT_COMPLETION = "chat_completion"
    QUERY_EMBEDDING = "query_embedding"
    INGEST_EMBEDDING = "ingest_embedding"


class UsageEvent(Base, UUIDPrimaryKeyMixin):
    """One provider call (or apportioned slice) with token + cost estimates."""

    __tablename__ = "usage_events"
    __table_args__ = (
        CheckConstraint(
            "kind IN ("
            "'suggestion', 'chat_completion', 'query_embedding', 'ingest_embedding'"
            ")",
            name="ck_usage_events_kind",
        ),
    )

    kind: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    model: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost_usd: Mapped[Decimal] = mapped_column(
        Numeric(12, 8),
        nullable=False,
        default=Decimal("0"),
    )
    thread_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_threads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    document_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    chunk_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("document_chunks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
