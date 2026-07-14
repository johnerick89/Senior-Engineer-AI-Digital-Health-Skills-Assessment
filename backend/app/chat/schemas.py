from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class ChatTurn(BaseModel):
    input: str
    response: str

    @field_validator("input", "response", mode="before")
    @classmethod
    def strip_and_require(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("must not be blank")
        return text


class ChatRequest(BaseModel):
    input: str
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)
    id: uuid.UUID | None = Field(
        default=None,
        description="Existing chat thread id; omit to start a new thread.",
    )

    @field_validator("input", mode="before")
    @classmethod
    def strip_input(cls, value: Any) -> str:
        text = str(value or "").strip()
        if not text:
            raise ValueError("input must not be blank")
        return text


class ChatThreadSummary(BaseModel):
    id: uuid.UUID
    title: str | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    model: str | None = None


class ChatSuggestionsResponse(BaseModel):
    topics: list[str] = Field(default_factory=list, max_length=5)


class ChatUsageOut(BaseModel):
    thread_id: uuid.UUID
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class UsageBucketOut(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0


class UsageSummaryOut(BaseModel):
    chats: UsageBucketOut
    suggestions: UsageBucketOut
    embeddings: UsageBucketOut
    total_tokens: int = 0
    estimated_cost_usd: float = 0.0
