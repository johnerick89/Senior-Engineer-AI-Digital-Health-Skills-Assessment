"""Grounded LLM generation with retrieval context and streaming."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from rag_core.core.config import get_settings
from rag_core.core.logging import get_logger
from rag_core.core.openai_client import create_chat_completion
from rag_core.db.session import get_session
from rag_core.rag.reranking import rerank_chunks
from rag_core.rag.retrieval import retrieve_chunks_async
from rag_core.rag.schemas import ChatQuery, ChatTurn, RetrievedChunk
from rag_core.services.document_service import list_ready_document_filenames

logger = get_logger(__name__)

SYSTEM_INSTRUCTIONS = """You are a helpful assistant for Last Mile Health document Q&A.
Rules:
- Answer using the provided document context. Prefer the context over prior assumptions.
- If the context fully or partially answers the question, give a clear answer and cite sources as [filename, page N] when page is known, or [filename] otherwise.
- If the context is insufficient, say so briefly — do not invent facts outside the context.
- Be concise and practical.
"""


def format_no_match_answer(filenames: list[str]) -> str:
    """Fallback when retrieval finds nothing relevant: what the user can ask about."""
    if not filenames:
        return (
            "I don't have any uploaded documents to answer from yet. "
            "Please upload one or more PDFs on the Upload page, then ask again."
        )
    lines = "\n".join(f"- {name}" for name in filenames[:10])
    return (
        "I couldn't find that in the uploaded documents. "
        "I can answer questions related to these:\n"
        f"{lines}"
    )


# Back-compat alias for the empty-corpus fallback text.
EMPTY_CORPUS_MESSAGE = format_no_match_answer([])


def list_available_documents(limit: int = 10) -> list[str]:
    """Load ready document filenames (sync Session)."""
    with get_session() as db:
        return list_ready_document_filenames(db, limit=limit)


def format_context_blocks(chunks: list[RetrievedChunk]) -> str:
    """Render retrieved chunks into a numbered context block for the prompt."""
    if not chunks:
        return "(no context)"

    parts: list[str] = []
    for i, chunk in enumerate(chunks, start=1):
        page = (
            f", page {chunk.page_number}"
            if chunk.page_number is not None
            else ""
        )
        header = f"[{i}] {chunk.filename}{page} (chunk {chunk.chunk_index})"
        parts.append(f"{header}\n{chunk.content.strip()}")
    return "\n\n".join(parts)


def build_rag_messages(
    *,
    user_input: str,
    history: list[ChatTurn],
    chunks: list[RetrievedChunk],
) -> list[dict[str, Any]]:
    """Build chat messages: system + history + context-augmented user turn."""
    context = format_context_blocks(chunks)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_INSTRUCTIONS},
    ]
    for turn in history:
        messages.append({"role": "user", "content": turn.input})
        messages.append({"role": "assistant", "content": turn.response})

    user_content = (
        f"Document context:\n{context}\n\n"
        f"User question:\n{user_input.strip()}"
    )
    messages.append({"role": "user", "content": user_content})
    return messages


async def stream_chat_tokens(
    messages: list[dict[str, Any]],
    *,
    model: str | None = None,
) -> AsyncIterator[str]:
    """Yield content deltas from a streamed chat completion."""
    settings = get_settings()
    resolved_model = model or settings.generation_model
    stream = await create_chat_completion(
        model=resolved_model,
        messages=messages,
        stream=True,
    )
    async for event in stream:
        choices = getattr(event, "choices", None) or []
        if not choices:
            continue
        delta = getattr(choices[0], "delta", None)
        content = getattr(delta, "content", None) if delta is not None else None
        if content:
            yield content


async def _yield_text(text: str) -> AsyncIterator[str]:
    if text:
        yield text


async def stream_rag_answer(query: ChatQuery) -> AsyncIterator[str]:
    """Retrieve → rerank → stream grounded answer, or document catalog on miss."""
    chunks, query_embedding = await retrieve_chunks_async(query.input)
    selected = (
        rerank_chunks(query_embedding, chunks) if chunks and query_embedding else []
    )

    if not selected:
        titles = await asyncio.to_thread(list_available_documents, 10)
        logger.info(
            "rag_no_match_fallback",
            retrieved=len(chunks),
            document_count=len(titles),
        )
        async for part in _yield_text(format_no_match_answer(titles)):
            yield part
        return

    messages = build_rag_messages(
        user_input=query.input,
        history=query.history,
        chunks=selected,
    )
    logger.info(
        "rag_generation_start",
        context_chunks=len(selected),
        history_turns=len(query.history),
    )
    async for token in stream_chat_tokens(messages):
        yield token
