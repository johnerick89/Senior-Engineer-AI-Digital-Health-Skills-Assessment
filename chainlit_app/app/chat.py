"""Chainlit handlers: RAG chat via rag_core, shared thread history, starters."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Optional

import chainlit as cl

from app.data_layer import ANONYMOUS_USER_ID, RagCoreDataLayer
from app.turn import ensure_thread, history_for_query, persist_turn_usage
from rag_core.rag.generation import RagStreamCapture, stream_rag_answer
from rag_core.rag.schemas import ChatQuery
from rag_core.rag.suggestions import suggest_chat_topics
from rag_core.rag.vector_store import initialize_vector_store

logger = logging.getLogger(__name__)

_INIT_DONE = False


def _ensure_schema() -> None:
    global _INIT_DONE
    if _INIT_DONE:
        return
    try:
        initialize_vector_store()
    except Exception:
        logger.exception("vector_store_init_failed")
    _INIT_DONE = True


@cl.data_layer
def get_data_layer() -> RagCoreDataLayer:
    """Register the rag_core-backed history sidebar."""
    return RagCoreDataLayer()


@cl.password_auth_callback
def auth_callback(username: str, password: str) -> Optional[cl.User]:
    """Accept any login; all sessions share the anonymous thread list."""
    _ = password
    return cl.User(
        identifier=ANONYMOUS_USER_ID,
        display_name=(username or "Guest").strip() or "Guest",
        metadata={"provider": "credentials"},
    )


@cl.set_starters
async def set_starters() -> list[cl.Starter]:
    """Document-grounded starter topics for a new chat."""
    try:
        topics = await suggest_chat_topics()
    except Exception:
        logger.exception("suggest_chat_topics_failed")
        return []
    return [
        cl.Starter(label=topic[:80], message=topic)
        for topic in topics
        if topic and topic.strip()
    ]


def _session_thread_id() -> uuid.UUID | None:
    raw = cl.user_session.get("thread_id")
    if raw:
        try:
            return uuid.UUID(str(raw))
        except ValueError:
            pass
    ctx_id = getattr(getattr(cl.context, "session", None), "thread_id", None)
    if ctx_id:
        try:
            return uuid.UUID(str(ctx_id))
        except ValueError:
            return None
    return None


@cl.on_chat_start
async def on_chat_start() -> None:
    """Bind session thread id for a new chat."""
    await asyncio.to_thread(_ensure_schema)
    thread_id = getattr(getattr(cl.context, "session", None), "thread_id", None)
    if thread_id:
        cl.user_session.set("thread_id", str(thread_id))
    else:
        cl.user_session.set("thread_id", None)


@cl.on_chat_resume
async def on_chat_resume(thread: dict) -> None:
    """Resume a shared thread from the history sidebar."""
    await asyncio.to_thread(_ensure_schema)
    thread_id = thread.get("id") if isinstance(thread, dict) else None
    if thread_id:
        cl.user_session.set("thread_id", str(thread_id))


@cl.on_message
async def on_message(message: cl.Message) -> None:
    """Stream a RAG answer and persist the turn (same path as backend /chat)."""
    await asyncio.to_thread(_ensure_schema)

    text = (message.content or "").strip()
    if not text:
        await cl.Message(content="Please enter a question.").send()
        return

    existing_id = _session_thread_id()
    history = await asyncio.to_thread(history_for_query, existing_id)

    try:
        thread_id, _title = await asyncio.to_thread(
            ensure_thread,
            text,
            thread_id=existing_id,
        )
    except ValueError:
        await cl.Message(content="Please enter a question.").send()
        return
    except Exception:
        logger.exception("ensure_thread_failed")
        await cl.Message(
            content="Could not save your message. Check the database connection."
        ).send()
        return

    cl.user_session.set("thread_id", str(thread_id))

    query = ChatQuery(input=text, history=history)
    capture = RagStreamCapture()
    reply = cl.Message(content="")
    await reply.send()

    parts: list[str] = []
    try:
        async for chunk in stream_rag_answer(query, capture=capture):
            parts.append(chunk)
            await reply.stream_token(chunk)
    except Exception:
        logger.exception("rag_stream_failed")
        error_text = "Sorry — something went wrong generating a response."
        if not parts:
            reply.content = error_text
            await reply.update()
        await asyncio.to_thread(
            persist_turn_usage,
            thread_id,
            assistant_content="".join(parts) or error_text,
            capture=capture,
        )
        return

    await reply.update()
    await asyncio.to_thread(
        persist_turn_usage,
        thread_id,
        assistant_content="".join(parts),
        capture=capture,
    )
