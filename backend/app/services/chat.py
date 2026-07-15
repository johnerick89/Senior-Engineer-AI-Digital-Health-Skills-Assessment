"""Chat thread and usage persistence helpers."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.schemas.chat import ChatRequest, UsageBucketOut
from rag_core.db.session import get_session
from rag_core.models.usage_event import UsageKind
from rag_core.rag.generation import RagStreamCapture
from rag_core.services import chat_service
from rag_core.services.usage_service import (
    apply_usage_to_message,
    record_usage_event,
)


def touch_thread(thread) -> None:
    """Bump thread updated_at after a new message."""
    thread.updated_at = datetime.now(timezone.utc)


def ensure_thread(request: ChatRequest) -> tuple[uuid.UUID, str]:
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
        touch_thread(thread)
        db.commit()
        db.refresh(thread)
        return thread.id, thread.title or title


def persist_turn_usage(
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

        touch_thread(thread)
        db.commit()


def bucket_out(bucket) -> UsageBucketOut:
    """Map a rag_core usage bucket to an API schema."""
    return UsageBucketOut(
        prompt_tokens=bucket.prompt_tokens,
        completion_tokens=bucket.completion_tokens,
        total_tokens=bucket.total_tokens,
        estimated_cost_usd=round(bucket.estimated_cost_usd, 8),
    )
