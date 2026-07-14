"""Pydantic schemas for the chat RAG API surface."""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator


class ChatTurn(BaseModel):
    """One prior user/assistant exchange."""

    input: str
    response: str

    @field_validator("input", "response", mode="before")
    @classmethod
    def strip_and_require(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("must not be blank")
        return text


class ChatQuery(BaseModel):
    """Validated chat request for rag_core orchestration."""

    input: str
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)

    @field_validator("input", mode="before")
    @classmethod
    def strip_input(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("input must not be blank")
        return text


class RetrievedChunk(BaseModel):
    """A retrieved document chunk with similarity score and embedding for MMR."""

    content: str
    document_id: uuid.UUID
    filename: str
    chunk_index: int
    page_number: int | None = None
    score: float = Field(description="Cosine similarity in [0, 1] (approx).")
    embedding: list[float] = Field(default_factory=list, exclude=True)
