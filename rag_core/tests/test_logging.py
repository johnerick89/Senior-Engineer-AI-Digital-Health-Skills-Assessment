"""Tests for rag_core.core.logging."""

from unittest.mock import MagicMock, patch

from rag_core.core import logging as rag_logging
from rag_core.core.logging import configure_logging, get_logger


def test_get_logger_returns_usable_logger() -> None:
    configure_logging()
    logger = get_logger("rag_core.tests")
    assert hasattr(logger, "info")
    assert hasattr(logger, "bind")


@patch("rag_core.core.logging.structlog.configure")
def test_configure_logging_uses_console_renderer_outside_production(
    mock_configure: MagicMock,
) -> None:
    mock_settings = MagicMock(app_env="development", log_level="INFO")
    with patch.object(rag_logging, "settings", mock_settings):
        configure_logging()

    processors = mock_configure.call_args.kwargs["processors"]
    assert any(type(p).__name__ == "ConsoleRenderer" for p in processors)
    assert not any(type(p).__name__ == "JSONRenderer" for p in processors)


@patch("rag_core.core.logging.structlog.configure")
def test_configure_logging_uses_json_renderer_in_production(
    mock_configure: MagicMock,
) -> None:
    mock_settings = MagicMock(app_env="production", log_level="WARNING")
    with patch.object(rag_logging, "settings", mock_settings):
        configure_logging()

    processors = mock_configure.call_args.kwargs["processors"]
    assert any(type(p).__name__ == "JSONRenderer" for p in processors)
    assert not any(type(p).__name__ == "ConsoleRenderer" for p in processors)
