"""Central LLM client: OpenAI primary, OpenRouter fallback.

Call sites should use ``create_embeddings`` / ``create_chat_completion`` so
provider selection and OpenRouter ``openai/`` model prefixes stay in one place.
"""

from __future__ import annotations

from typing import Any

from openai import APIError, AsyncOpenAI, RateLimitError

from rag_core.core.config import get_settings
from rag_core.core.logging import get_logger

logger = get_logger(__name__)

_OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

_openai_client: AsyncOpenAI | None = None
_openrouter_client: AsyncOpenAI | None = None


def openrouter_model_id(model: str) -> str:
    """Map an OpenAI model id to OpenRouter's ``openai/<model>`` form."""
    if model.startswith("openai/"):
        return model
    return f"openai/{model}"


def reset_async_client() -> None:
    """Clear OpenAI and OpenRouter singletons (useful in tests)."""
    global _openai_client, _openrouter_client
    _openai_client = None
    _openrouter_client = None


def get_async_client() -> AsyncOpenAI:
    """Return the primary OpenAI AsyncOpenAI client.

    Prefer ``create_embeddings`` / ``create_chat_completion`` for calls that
    should fall back to OpenRouter.
    """
    global _openai_client
    if _openai_client is None:
        settings = get_settings()
        if not settings.openai_api_key:
            raise RuntimeError(
                "OpenAI is not configured. Set OPENAI_API_KEY in your environment."
            )
        _openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
    return _openai_client


def get_openrouter_async_client() -> AsyncOpenAI:
    """Return the OpenRouter AsyncOpenAI-compatible client."""
    global _openrouter_client
    if _openrouter_client is None:
        settings = get_settings()
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OpenRouter is not configured. Set OPENROUTER_API_KEY in your environment."
            )
        _openrouter_client = AsyncOpenAI(
            base_url=_OPENROUTER_BASE_URL,
            api_key=settings.openrouter_api_key,
        )
    return _openrouter_client


def _should_fallback(exc: BaseException) -> bool:
    """Return True for API / quota failures worth retrying on OpenRouter."""
    return isinstance(exc, (RateLimitError, APIError))


async def create_embeddings(
    *,
    model: str,
    input: list[str],
    **kwargs: Any,
) -> Any:
    """Create embeddings via OpenAI, falling back to OpenRouter on failure.

    OpenRouter model ids use the ``openai/<name>`` prefix
    (e.g. ``openai/text-embedding-3-small``).
    """
    settings = get_settings()
    errors: list[str] = []

    if settings.openai_api_key:
        try:
            client = get_async_client()
            return await client.embeddings.create(model=model, input=input, **kwargs)
        except Exception as exc:
            if not settings.openrouter_api_key or not _should_fallback(exc):
                raise
            errors.append(f"openai: {exc}")
            logger.warning(
                "openai_embeddings_failed_falling_back_to_openrouter",
                error=str(exc),
                model=model,
            )

    if settings.openrouter_api_key:
        client = get_openrouter_async_client()
        routed_model = openrouter_model_id(model)
        return await client.embeddings.create(
            model=routed_model,
            input=input,
            **kwargs,
        )

    detail = "; ".join(errors) if errors else "no provider keys configured"
    raise RuntimeError(
        "No LLM provider available for embeddings. "
        "Set OPENAI_API_KEY and/or OPENROUTER_API_KEY. "
        f"({detail})"
    )


async def create_chat_completion(
    *,
    model: str,
    messages: list[dict[str, Any]],
    **kwargs: Any,
) -> Any:
    """Create a chat completion via OpenAI, falling back to OpenRouter on failure.

    OpenRouter model ids use the ``openai/<name>`` prefix
    (e.g. ``openai/gpt-4o-mini``).
    """
    settings = get_settings()
    errors: list[str] = []

    if settings.openai_api_key:
        try:
            client = get_async_client()
            return await client.chat.completions.create(
                model=model,
                messages=messages,
                **kwargs,
            )
        except Exception as exc:
            if not settings.openrouter_api_key or not _should_fallback(exc):
                raise
            errors.append(f"openai: {exc}")
            logger.warning(
                "openai_chat_failed_falling_back_to_openrouter",
                error=str(exc),
                model=model,
            )

    if settings.openrouter_api_key:
        client = get_openrouter_async_client()
        routed_model = openrouter_model_id(model)
        return await client.chat.completions.create(
            model=routed_model,
            messages=messages,
            **kwargs,
        )

    detail = "; ".join(errors) if errors else "no provider keys configured"
    raise RuntimeError(
        "No LLM provider available for chat completion. "
        "Set OPENAI_API_KEY and/or OPENROUTER_API_KEY. "
        f"({detail})"
    )
