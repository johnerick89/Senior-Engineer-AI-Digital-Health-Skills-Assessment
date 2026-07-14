"""Tests for rag_core.db.connection."""

from unittest.mock import MagicMock, patch

import psycopg

from rag_core.core.config import Settings
from rag_core.db.connection import check_connection, connect


@patch("rag_core.db.connection.psycopg.connect")
def test_connect_uses_explicit_database_url(mock_connect: MagicMock) -> None:
    mock_connect.return_value = MagicMock()

    connect("postgresql://example:5432/app")

    mock_connect.assert_called_once_with("postgresql://example:5432/app")


@patch("rag_core.db.connection.psycopg.connect")
def test_connect_uses_settings_when_url_not_provided(
    mock_connect: MagicMock,
    isolated_settings_env: None,
) -> None:
    mock_connect.return_value = MagicMock()
    settings = Settings(_env_file=None, database_url="postgresql://settings:5432/rag")

    connect(settings=settings)

    mock_connect.assert_called_once_with("postgresql://settings:5432/rag")


@patch("rag_core.db.connection.connect")
def test_check_connection_returns_true_on_success(mock_connect: MagicMock) -> None:
    conn = MagicMock()
    mock_connect.return_value.__enter__.return_value = conn

    assert check_connection("postgresql://example:5432/app") is True
    conn.execute.assert_called_once_with("SELECT 1")


@patch("rag_core.db.connection.connect", side_effect=psycopg.OperationalError)
def test_check_connection_returns_false_on_error(_mock_connect: MagicMock) -> None:
    assert check_connection("postgresql://example:5432/app") is False
