"""Document ORM model."""

from __future__ import annotations

from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from rag_core.models.base import BaseModel

if TYPE_CHECKING:
    from rag_core.models.document_chunk import DocumentChunk


class DocumentStatus(str, Enum):
    """Lifecycle status for an ingested document."""

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class Document(BaseModel):
    """Uploaded source document (PDF)."""

    __tablename__ = "documents"

    filename: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=DocumentStatus.PROCESSING.value,
        server_default=text("'processing'"),
    )

    chunks: Mapped[list[DocumentChunk]] = relationship(
        "DocumentChunk",
        back_populates="document",
        cascade="all, delete-orphan",
    )
