"""Generate starter chat topics from uploaded documents."""

from __future__ import annotations

import json
import re
from typing import Any

from rag_core.core.config import get_settings
from rag_core.core.logging import get_logger
from rag_core.core.openai_client import create_chat_completion
from rag_core.db.session import get_session
from rag_core.models.usage_event import UsageKind
from rag_core.services.document_service import (
    DocumentSnippet,
    sample_ready_document_snippets,
)
from rag_core.services.usage_service import (
    record_usage_event,
    usage_from_openai_response,
)

logger = get_logger(__name__)

MAX_TOPICS = 5

_TOPIC_SYSTEM = """You propose short starter questions for a document Q&A assistant.
Return ONLY a JSON array of strings (no markdown fences). At most 5 items.
Each string must be a specific question grounded in the supplied document snippets.
Questions must be unique from each other and clearly tied to the content (not generic).
Keep each question under 120 characters.
"""


def _fallback_topics(snippets: list[DocumentSnippet], *, limit: int) -> list[str]:
    """Deterministic topics from filenames / snippet lead-ins when the LLM fails."""
    topics: list[str] = []
    seen: set[str] = set()
    for snippet in snippets:
        stem = re.sub(r"\.pdf$", "", snippet.filename, flags=re.IGNORECASE)
        stem = re.sub(r"\s+", " ", stem).strip()
        if not stem:
            continue
        lead = snippet.content.split(".")[0].strip()
        if lead and len(lead) > 20:
            question = f"What does the document say about: {lead[:80]}?"
        else:
            question = f"Summarize the key points in {stem}."
        key = question.lower()
        if key in seen:
            continue
        seen.add(key)
        topics.append(question)
        if len(topics) >= limit:
            break
    return topics


def _parse_topics(raw: str, *, limit: int) -> list[str]:
    text = raw.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        data: Any = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            return []
        try:
            data = json.loads(match.group(0))
        except json.JSONDecodeError:
            return []

    if not isinstance(data, list):
        return []

    topics: list[str] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, str):
            continue
        q = " ".join(item.split()).strip()
        if not q or len(q) < 8:
            continue
        if len(q) > 160:
            q = q[:159].rstrip() + "…"
        key = q.lower()
        if key in seen:
            continue
        seen.add(key)
        topics.append(q)
        if len(topics) >= limit:
            break
    return topics


def _format_snippet_block(snippets: list[DocumentSnippet]) -> str:
    parts: list[str] = []
    for i, snippet in enumerate(snippets, start=1):
        page = f", page {snippet.page_number}" if snippet.page_number is not None else ""
        parts.append(f"[{i}] {snippet.filename}{page}\n{snippet.content}")
    return "\n\n".join(parts)


async def suggest_chat_topics(*, limit: int = MAX_TOPICS) -> list[str]:
    """Inspect ready documents/chunks and return up to ``limit`` starter questions."""
    cap = max(0, min(limit, MAX_TOPICS))
    if cap == 0:
        return []

    with get_session() as db:
        snippets = sample_ready_document_snippets(db, limit=8)

    if not snippets:
        logger.info("chat_topics_no_documents")
        return []

    fallback = _fallback_topics(snippets, limit=cap)
    settings = get_settings()
    prompt = (
        "Document samples:\n"
        f"{_format_snippet_block(snippets)}\n\n"
        f"Propose up to {cap} distinct starter questions a user might ask."
    )

    try:
        response = await create_chat_completion(
            model=settings.generation_model,
            messages=[
                {"role": "system", "content": _TOPIC_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.4,
        )
        content = response.choices[0].message.content or ""
        topics = _parse_topics(content, limit=cap)
        usage = usage_from_openai_response(
            response,
            model=settings.generation_model,
            is_embedding=False,
        )
        with get_session() as db:
            record_usage_event(db, kind=UsageKind.SUGGESTION, usage=usage)
            db.commit()
        if topics:
            logger.info(
                "chat_topics_generated",
                count=len(topics),
                source="llm",
                tokens=usage.total_tokens,
            )
            return topics
    except Exception as exc:
        logger.warning("chat_topics_llm_failed", error=str(exc))

    logger.info("chat_topics_generated", count=len(fallback), source="fallback")
    return fallback
