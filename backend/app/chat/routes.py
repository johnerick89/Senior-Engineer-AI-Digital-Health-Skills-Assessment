"""Chat streaming and thread history endpoints."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.chat.schemas import (
    ChatMessageOut,
    ChatRequest,
    ChatSuggestionsResponse,
    ChatThreadSummary,
    ChatUsageOut,
    UsageBucketOut,
    UsageSummaryOut,
)
from rag_core.db.session import get_session
from rag_core.models.usage_event import UsageKind
from rag_core.rag.generation import RagStreamCapture, stream_rag_answer
from rag_core.rag.schemas import ChatQuery, ChatTurn as RagChatTurn
from rag_core.rag.suggestions import suggest_chat_topics
from rag_core.services import chat_service
from rag_core.services.usage_service import (
    apply_usage_to_message,
    record_usage_event,
    summarize_app_usage,
    summarize_thread_usage,
)

router = APIRouter()

CHAT_ID_HEADER = "X-Chat-Id"
CHAT_TITLE_HEADER = "X-Chat-Title"


def _touch_thread(thread) -> None:
    thread.updated_at = datetime.now(timezone.utc)


def _ensure_thread(request: ChatRequest) -> tuple[uuid.UUID, str]:
    """Create or load a thread, persist the user message, return (id, title)."""
    with get_session() as db:
        if request.id is not None:
            thread = chat_service.get_thread(db, request.id)
            if thread is None:
                raise LookupError("missing")
            prior_user_count = chat_service.count_user_messages(db, thread.id)
            title = chat_service.derive_thread_title(
                request.input,
                existing_title=thread.title,
                user_message_count_before=prior_user_count,
            )
            if title != thread.title:
                chat_service.update_thread_title(db, thread, title)
        else:
            title = chat_service.derive_thread_title(
                request.input,
                existing_title=None,
                user_message_count_before=0,
            )
            thread = chat_service.create_thread(db, title=title)

        chat_service.add_message(
            db,
            thread.id,
            role="user",
            content=request.input,
        )
        _touch_thread(thread)
        db.commit()
        db.refresh(thread)
        return thread.id, thread.title or title


def _persist_turn_usage(
    thread_id: uuid.UUID,
    *,
    assistant_content: str,
    capture: RagStreamCapture,
) -> None:
    """Attach embed usage to the latest user message; save assistant + ledger rows."""
    with get_session() as db:
        thread = chat_service.get_thread(db, thread_id)
        if thread is None:
            return

        user_msg = chat_service.get_latest_user_message(db, thread_id)
        if user_msg is not None and capture.query_embed_usage is not None:
            apply_usage_to_message(user_msg, capture.query_embed_usage)
            record_usage_event(
                db,
                kind=UsageKind.QUERY_EMBEDDING,
                usage=capture.query_embed_usage,
                thread_id=thread_id,
                message_id=user_msg.id,
            )

        text = assistant_content.strip()
        if text:
            usage = capture.completion_usage
            message = chat_service.add_message(
                db,
                thread_id,
                role="assistant",
                content=text,
                prompt_tokens=usage.prompt_tokens if usage else None,
                completion_tokens=usage.completion_tokens if usage else None,
                total_tokens=usage.total_tokens if usage else None,
                estimated_cost_usd=usage.estimated_cost_usd if usage else None,
                model=usage.model if usage else None,
            )
            if usage is not None:
                record_usage_event(
                    db,
                    kind=UsageKind.CHAT_COMPLETION,
                    usage=usage,
                    thread_id=thread_id,
                    message_id=message.id,
                )

        _touch_thread(thread)
        db.commit()


def _bucket_out(bucket) -> UsageBucketOut:
    return UsageBucketOut(
        prompt_tokens=bucket.prompt_tokens,
        completion_tokens=bucket.completion_tokens,
        total_tokens=bucket.total_tokens,
        estimated_cost_usd=round(bucket.estimated_cost_usd, 8),
    )


@router.get("/chat/suggestions", response_model=ChatSuggestionsResponse)
async def chat_suggestions() -> ChatSuggestionsResponse:
    """Return up to five document-grounded starter topics for a new chat."""
    topics = await suggest_chat_topics()
    return ChatSuggestionsResponse(topics=topics)


@router.get("/chats", response_model=list[ChatThreadSummary])
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


@router.get("/chats/{thread_id}/messages", response_model=list[ChatMessageOut])
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


@router.get("/chats/{thread_id}/usage", response_model=ChatUsageOut)
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


@router.get("/usage/summary", response_model=UsageSummaryOut)
async def usage_summary() -> UsageSummaryOut:
    """App-wide usage rollup for the Usage page."""

    def _load() -> UsageSummaryOut:
        with get_session() as db:
            summary = summarize_app_usage(db)
            return UsageSummaryOut(
                chats=_bucket_out(summary.chats),
                suggestions=_bucket_out(summary.suggestions),
                embeddings=_bucket_out(summary.embeddings),
                total_tokens=summary.total_tokens,
                estimated_cost_usd=round(summary.estimated_cost_usd, 8),
            )

    return await asyncio.to_thread(_load)


@router.post("/chat")
async def chat(request: ChatRequest):
    """Stream a RAG answer and persist the turn on a chat thread."""
    try:
        thread_id, title = await asyncio.to_thread(_ensure_thread, request)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Chat thread not found") from exc

    query = ChatQuery(
        input=request.input,
        history=[
            RagChatTurn(input=turn.input, response=turn.response)
            for turn in request.history
        ],
    )
    capture = RagStreamCapture()

    async def generate() -> AsyncIterator[str]:
        parts: list[str] = []
        try:
            async for chunk in stream_rag_answer(query, capture=capture):
                parts.append(chunk)
                yield chunk
        finally:
            await asyncio.to_thread(
                _persist_turn_usage,
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
