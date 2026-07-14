"""Tests for rag_core.core.openai_client provider failover."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from openai import APIError

from rag_core.core import openai_client
from rag_core.core.config import get_settings
from rag_core.core.openai_client import (
    create_chat_completion,
    create_embeddings,
    get_async_client,
    openrouter_model_id,
    reset_async_client,
)


@pytest.fixture(autouse=True)
def _reset_client() -> None:
    reset_async_client()
    get_settings.cache_clear()
    yield
    reset_async_client()
    get_settings.cache_clear()


def test_openrouter_model_id_prefixes_openai() -> None:
    assert openrouter_model_id("gpt-4o-mini") == "openai/gpt-4o-mini"
    assert openrouter_model_id("text-embedding-3-small") == "openai/text-embedding-3-small"
    assert openrouter_model_id("openai/gpt-4o") == "openai/gpt-4o"


def test_get_async_client_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_settings.cache_clear()

    with patch.object(openai_client, "get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(openai_api_key="")
        with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
            get_async_client()


@patch("rag_core.core.openai_client.AsyncOpenAI")
def test_get_async_client_creates_client_with_api_key(
    mock_async_openai: MagicMock,
) -> None:
    mock_async_openai.return_value = MagicMock(name="client")

    with patch.object(openai_client, "get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(openai_api_key="sk-test")
        client = get_async_client()

    mock_async_openai.assert_called_once_with(api_key="sk-test")
    assert client is mock_async_openai.return_value


@patch("rag_core.core.openai_client.AsyncOpenAI")
def test_get_async_client_is_singleton(mock_async_openai: MagicMock) -> None:
    mock_async_openai.return_value = MagicMock(name="client")

    with patch.object(openai_client, "get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(openai_api_key="sk-test")
        first = get_async_client()
        second = get_async_client()

    assert first is second
    mock_async_openai.assert_called_once()


@patch("rag_core.core.openai_client.AsyncOpenAI")
def test_reset_async_client_allows_recreation(mock_async_openai: MagicMock) -> None:
    mock_async_openai.side_effect = [MagicMock(name="c1"), MagicMock(name="c2")]

    with patch.object(openai_client, "get_settings") as mock_get_settings:
        mock_get_settings.return_value = MagicMock(openai_api_key="sk-test")
        first = get_async_client()
        reset_async_client()
        second = get_async_client()

    assert first is not second
    assert mock_async_openai.call_count == 2


@pytest.mark.asyncio
async def test_create_embeddings_falls_back_to_openrouter() -> None:
    openai_client_mock = MagicMock()
    openai_client_mock.embeddings.create = AsyncMock(
        side_effect=APIError("quota", request=None, body=None)
    )
    openrouter_client_mock = MagicMock()
    expected = MagicMock(name="embedding_response")
    openrouter_client_mock.embeddings.create = AsyncMock(return_value=expected)

    settings = MagicMock(
        openai_api_key="sk-openai",
        openrouter_api_key="sk-or",
    )

    with (
        patch.object(openai_client, "get_settings", return_value=settings),
        patch.object(openai_client, "get_async_client", return_value=openai_client_mock),
        patch.object(
            openai_client,
            "get_openrouter_async_client",
            return_value=openrouter_client_mock,
        ),
    ):
        result = await create_embeddings(model="text-embedding-3-small", input=["hi"])

    assert result is expected
    openrouter_client_mock.embeddings.create.assert_awaited_once_with(
        model="openai/text-embedding-3-small",
        input=["hi"],
    )


@pytest.mark.asyncio
async def test_create_chat_completion_uses_openrouter_only_when_openai_unset() -> None:
    openrouter_client_mock = MagicMock()
    expected = MagicMock(name="chat_response")
    openrouter_client_mock.chat.completions.create = AsyncMock(return_value=expected)

    settings = MagicMock(openai_api_key="", openrouter_api_key="sk-or")

    with (
        patch.object(openai_client, "get_settings", return_value=settings),
        patch.object(
            openai_client,
            "get_openrouter_async_client",
            return_value=openrouter_client_mock,
        ),
    ):
        result = await create_chat_completion(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": "Hello!"}],
        )

    assert result is expected
    openrouter_client_mock.chat.completions.create.assert_awaited_once_with(
        model="openai/gpt-4o-mini",
        messages=[{"role": "user", "content": "Hello!"}],
    )
