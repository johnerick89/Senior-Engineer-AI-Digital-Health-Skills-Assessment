"""ChatThread ORM model."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_core.models.base import BaseModel

if TYPE_CHECKING:
    from rag_core.models.chat_message import ChatMessage


class ChatThread(BaseModel):
    """Conversation thread for chat history."""

    __tablename__ = "chat_threads"

    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    messages: Mapped[list[ChatMessage]] = relationship(
        "ChatMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
