"""Tests for rag_core.core.openai_client."""

from unittest.mock import MagicMock, patch

import pytest

from rag_core.core import openai_client
from rag_core.core.config import get_settings
from rag_core.core.openai_client import get_async_client, reset_async_client


@pytest.fixture(autouse=True)
def _reset_client() -> None:
    reset_async_client()
    get_settings.cache_clear()
    yield
    reset_async_client()
    get_settings.cache_clear()


def test_get_async_client_raises_when_api_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "")
    get_settings.cache_clear()
    # Empty string from env still loads; force empty via Settings by clearing env.
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
