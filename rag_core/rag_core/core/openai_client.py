"""Singleton factory for the shared AsyncOpenAI client.

Requires ``OPENAI_API_KEY``. The connection pool is shared and tests can
override the instance in one place via ``reset_async_client()``.
"""

from openai import AsyncOpenAI

from rag_core.core.config import get_settings

_client: AsyncOpenAI | None = None


def get_async_client() -> AsyncOpenAI:
    """Return the process-level AsyncOpenAI singleton, creating it on first call.

    Raises ``RuntimeError`` if ``OPENAI_API_KEY`` is not configured.
    """
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def _build_client() -> AsyncOpenAI:
    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError(
            "No LLM provider configured. Set OPENAI_API_KEY in your environment."
        )
    return AsyncOpenAI(api_key=settings.openai_api_key)


def reset_async_client() -> None:
    """Clear the singleton (useful in tests)."""
    global _client
    _client = None
