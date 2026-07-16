"""Chat streaming and thread history endpoints."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.logging import get_logger, log_event
from app.core.rate_limiter import limiter

from app.schemas.chat import (
    ChatMessageOut,
    ChatRequest,
    ChatSuggestionsResponse,
    ChatThreadSummary,
    ChatUsageOut,
)
from app.services.chat import ensure_thread, persist_turn_usage
from rag_core.db.session import get_session
from rag_core.rag.generation import RagStreamCapture, stream_rag_answer
from rag_core.rag.schemas import ChatQuery, ChatTurn as RagChatTurn
from rag_core.rag.suggestions import suggest_chat_topics
from rag_core.services import chat_service
from rag_core.services.usage_service import summarize_thread_usage

router = APIRouter(prefix="/chats", tags=["chats"])
logger = get_logger(__name__)

CHAT_ID_HEADER = "X-Chat-Id"
CHAT_TITLE_HEADER = "X-Chat-Title"


@router.get("/suggestions", response_model=ChatSuggestionsResponse)
async def chat_suggestions() -> ChatSuggestionsResponse:
    """Return up to five document-grounded starter topics for a new chat."""
    topics = await suggest_chat_topics()
    return ChatSuggestionsResponse(topics=topics)


@router.get("", response_model=list[ChatThreadSummary])
async def list_chats() -> list[ChatThreadSummary]:
    """Return recent chat threads for the sidebar."""

    def _load() -> list[ChatThreadSummary]:
        with get_session() as db:
            threads = chat_service.list_threads(db)
            return [
                ChatThreadSummary(
                    id=thread.id,
                    title=thread.title,
                    updated_at=thread.updated_at,
                    created_at=thread.created_at,
                )
                for thread in threads
            ]

    return await asyncio.to_thread(_load)


@router.post("")
@limiter.limit("20/minute")
async def create_chat(request: Request, chat_request: ChatRequest):
    """Stream a RAG answer and persist the turn on a chat thread."""
    try:
        thread_id, title = await asyncio.to_thread(ensure_thread, chat_request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Chat thread not found") from exc

    query = ChatQuery(
        input=chat_request.input,
        history=[
            RagChatTurn(input=turn.input, response=turn.response)
            for turn in chat_request.history
        ],
    )
    capture = RagStreamCapture()

    async def generate() -> AsyncIterator[str]:
        parts: list[str] = []
        start = time.perf_counter()
        try:
            async for chunk in stream_rag_answer(query, capture=capture):
                parts.append(chunk)
                yield chunk
        except Exception as exc:  # noqa: BLE001
            log_event(
                logger,
                "chat.request.failed",
                event="chat.request.failed",
                thread_id=str(thread_id),
                error=str(exc),
            )
            raise
        finally:
            duration_ms = int((time.perf_counter() - start) * 1000)
            embed_usage = capture.query_embed_usage
            completion_usage = capture.completion_usage
            embed_cost = embed_usage.estimated_cost_usd if embed_usage else Decimal("0")
            completion_cost = (
                completion_usage.estimated_cost_usd if completion_usage else Decimal("0")
            )
            total_cost = embed_cost + completion_cost
            log_event(
                logger,
                "chat.request.completed",
                event="chat.request.completed",
                thread_id=str(thread_id),
                thread_title=title,
                retrieval_chunk_count=len(capture.retrieved_chunks or []),
                selected_chunk_count=len(capture.selected_chunks or []),
                prompt_tokens=(
                    (embed_usage.prompt_tokens if embed_usage else 0)
                    + (completion_usage.prompt_tokens if completion_usage else 0)
                ),
                completion_tokens=(
                    (embed_usage.completion_tokens if embed_usage else 0)
                    + (completion_usage.completion_tokens if completion_usage else 0)
                ),
                total_tokens=(
                    (embed_usage.total_tokens if embed_usage else 0)
                    + (completion_usage.total_tokens if completion_usage else 0)
                ),
                estimated_cost_usd=total_cost,
                latency_ms=duration_ms,
                response_length=len("".join(parts)),
            )
            await asyncio.to_thread(
                persist_turn_usage,
                thread_id,
                assistant_content="".join(parts),
                capture=capture,
            )

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            CHAT_ID_HEADER: str(thread_id),
            CHAT_TITLE_HEADER: quote(title, safe=""),
            "Access-Control-Expose-Headers": f"{CHAT_ID_HEADER}, {CHAT_TITLE_HEADER}",
        },
    )


@router.get("/{thread_id}/messages", response_model=list[ChatMessageOut])
async def get_chat_messages(thread_id: uuid.UUID) -> list[ChatMessageOut]:
    """Return messages for a single thread in chronological order."""

    def _load() -> list[ChatMessageOut]:
        with get_session() as db:
            thread = chat_service.get_thread(db, thread_id)
            if thread is None:
                raise LookupError("missing")
            messages = chat_service.list_messages(db, thread_id)
            return [
                ChatMessageOut(
                    id=message.id,
                    role=message.role,  # type: ignore[arg-type]
                    content=message.content,
                    created_at=message.created_at,
                    prompt_tokens=message.prompt_tokens,
                    completion_tokens=message.completion_tokens,
                    total_tokens=message.total_tokens,
                    estimated_cost_usd=(
                        float(message.estimated_cost_usd)
                        if message.estimated_cost_usd is not None
                        else None
                    ),
                    model=message.model,
                )
                for message in messages
            ]

    try:
        return await asyncio.to_thread(_load)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Chat thread not found") from exc


@router.get("/{thread_id}/usage", response_model=ChatUsageOut)
async def get_chat_usage(thread_id: uuid.UUID) -> ChatUsageOut:
    """Return aggregated token/cost for one thread."""

    def _load() -> ChatUsageOut:
        with get_session() as db:
            thread = chat_service.get_thread(db, thread_id)
            if thread is None:
                raise LookupError("missing")
            summary = summarize_thread_usage(db, thread_id)
            return ChatUsageOut(
                thread_id=thread_id,
                prompt_tokens=summary.prompt_tokens,
                completion_tokens=summary.completion_tokens,
                total_tokens=summary.total_tokens,
                estimated_cost_usd=round(summary.estimated_cost_usd, 8),
            )

    try:
        return await asyncio.to_thread(_load)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Chat thread not found") from exc
