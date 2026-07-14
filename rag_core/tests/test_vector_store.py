"""Tests for rag_core.vector_store."""

from unittest.mock import MagicMock, patch

import pytest

from rag_core.core.config import Settings
from rag_core.vector_store import initialize_vector_store, vector_store_is_ready


@patch("rag_core.vector_store.connect")
@patch("rag_core.vector_store.register_vector")
@patch("rag_core.vector_store.apply_schema")
def test_initialize_vector_store_applies_schema_and_commits(
    mock_apply_schema: MagicMock,
    mock_register_vector: MagicMock,
    mock_connect: MagicMock,
    isolated_settings_env: None,
) -> None:
    conn = MagicMock()
    mock_connect.return_value.__enter__.return_value = conn
    settings = Settings(
        _env_file=None,
        database_url="postgresql://settings:5432/rag",
    )

    initialize_vector_store(settings=settings)

    mock_connect.assert_called_once_with("postgresql://settings:5432/rag", settings=settings)
    mock_apply_schema.assert_called_once_with(conn, 1536)
    mock_register_vector.assert_called_once_with(conn)
    conn.commit.assert_called_once()


@patch("rag_core.vector_store.check_connection", return_value=False)
def test_vector_store_is_ready_false_when_db_unreachable(
    _mock_check: MagicMock,
    isolated_settings_env: None,
) -> None:
    settings = Settings(_env_file=None, database_url="postgresql://settings:5432/rag")

    assert vector_store_is_ready(settings=settings) is False


@patch("rag_core.vector_store.check_connection", return_value=True)
@patch("rag_core.vector_store.connect")
def test_vector_store_is_ready_true_when_all_tables_exist(
    mock_connect: MagicMock,
    _mock_check: MagicMock,
    isolated_settings_env: None,
) -> None:
    conn = MagicMock()
    conn.execute.return_value.fetchall.return_value = [
        ("documents",),
        ("document_chunks",),
        ("chat_threads",),
        ("chat_messages",),
    ]
    mock_connect.return_value.__enter__.return_value = conn
    settings = Settings(_env_file=None, database_url="postgresql://settings:5432/rag")

    assert vector_store_is_ready(settings=settings) is True


@pytest.mark.integration
def test_initialize_and_verify_vector_store(integration_database_url: str) -> None:
    settings = Settings(_env_file=None, database_url=integration_database_url)

    initialize_vector_store(settings=settings)

    assert vector_store_is_ready(settings=settings) is True
