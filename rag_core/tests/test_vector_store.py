"""Tests for rag_core.vector_store."""

from unittest.mock import MagicMock, patch

import pytest

from rag_core.core.config import Settings
from rag_core.vector_store import initialize_vector_store, vector_store_is_ready


@patch("rag_core.vector_store.configure_engine")
@patch("rag_core.vector_store.run_migrations")
def test_initialize_vector_store_runs_migrations_and_configures_engine(
    mock_run_migrations: MagicMock,
    mock_configure_engine: MagicMock,
    isolated_settings_env: None,
) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://settings:5432/rag",
    )

    initialize_vector_store(settings=settings)

    mock_run_migrations.assert_called_once_with(
        "postgresql://settings:5432/rag",
        settings=settings,
    )
    mock_configure_engine.assert_called_once_with(
        "postgresql://settings:5432/rag",
        settings=settings,
    )


@patch("rag_core.vector_store.check_connection", return_value=False)
def test_vector_store_is_ready_false_when_db_unreachable(
    _mock_check: MagicMock,
    isolated_settings_env: None,
) -> None:
    settings = Settings(_env_file=None, database_url="postgresql://settings:5432/rag")

    assert vector_store_is_ready(settings=settings) is False


@patch("rag_core.vector_store.check_connection", return_value=True)
@patch("rag_core.vector_store.inspect")
@patch("rag_core.vector_store.get_engine")
def test_vector_store_is_ready_true_when_all_tables_exist(
    mock_get_engine: MagicMock,
    mock_inspect: MagicMock,
    _mock_check: MagicMock,
    isolated_settings_env: None,
) -> None:
    mock_inspect.return_value.get_table_names.return_value = [
        "documents",
        "document_chunks",
        "chat_threads",
        "chat_messages",
    ]
    settings = Settings(_env_file=None, database_url="postgresql://settings:5432/rag")

    assert vector_store_is_ready(settings=settings) is True
    mock_get_engine.assert_called_once()


@pytest.mark.integration
def test_initialize_and_verify_vector_store(integration_database_url: str) -> None:
    settings = Settings(_env_file=None, database_url=integration_database_url)

    initialize_vector_store(settings=settings)

    assert vector_store_is_ready(settings=settings) is True
