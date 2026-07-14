"""Chat streaming and thread history endpoints."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from urllib.parse import quote

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.chat.schemas import ChatMessageOut, ChatRequest, ChatThreadSummary
from rag_core.db.session import get_session
from rag_core.rag.generation import stream_rag_answer
from rag_core.rag.schemas import ChatQuery, ChatTurn as RagChatTurn
from rag_core.services import chat_service

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


def _save_assistant_message(thread_id: uuid.UUID, content: str) -> None:
    text = content.strip()
    if not text:
        return
    with get_session() as db:
        thread = chat_service.get_thread(db, thread_id)
        if thread is None:
            return
        chat_service.add_message(
            db,
            thread_id,
            role="assistant",
            content=text,
        )
        _touch_thread(thread)
        db.commit()


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
                )
                for message in messages
            ]

    try:
        return await asyncio.to_thread(_load)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Chat thread not found") from exc


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

    async def generate() -> AsyncIterator[str]:
        parts: list[str] = []
        try:
            async for chunk in stream_rag_answer(query):
                parts.append(chunk)
                yield chunk
        finally:
            await asyncio.to_thread(_save_assistant_message, thread_id, "".join(parts))

    return StreamingResponse(
        generate(),
        media_type="text/plain",
        headers={
            CHAT_ID_HEADER: str(thread_id),
            # Percent-encode so non-ASCII titles are safe in HTTP headers.
            CHAT_TITLE_HEADER: quote(title, safe=""),
            "Access-Control-Expose-Headers": f"{CHAT_ID_HEADER}, {CHAT_TITLE_HEADER}",
        },
    )
