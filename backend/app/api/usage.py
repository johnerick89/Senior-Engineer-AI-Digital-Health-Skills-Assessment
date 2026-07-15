"""App-wide usage summary endpoint."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter

from app.schemas.chat import UsageSummaryOut
from app.services.chat import bucket_out
from rag_core.db.session import get_session
from rag_core.services.usage_service import summarize_app_usage

router = APIRouter(prefix="/usage", tags=["usage"])


@router.get("", response_model=UsageSummaryOut)
async def usage_summary() -> UsageSummaryOut:
    """App-wide usage rollup for the Usage page."""

    def _load() -> UsageSummaryOut:
        with get_session() as db:
            summary = summarize_app_usage(db)
            return UsageSummaryOut(
                chats=bucket_out(summary.chats),
                suggestions=bucket_out(summary.suggestions),
                embeddings=bucket_out(summary.embeddings),
                total_tokens=summary.total_tokens,
                estimated_cost_usd=round(summary.estimated_cost_usd, 8),
            )

    return await asyncio.to_thread(_load)
