"""Shared pytest fixtures for rag_core."""

import os

import pytest
from sqlalchemy import text

from rag_core.core.config import Settings
from rag_core.db.session import check_connection, get_engine

_SETTINGS_ENV_VARS = (
    "DATABASE_URL",
    "OPENAI_API_KEY",
    "RAG_CORE_GENERATION_MODEL",
    "RAG_CORE_MODEL",
    "RAG_CORE_RETRIEVAL_K",
    "RAG_CORE_INGESTION_BATCH_SIZE",
    "RAG_CORE_STEP_TIMEOUT_SECONDS",
)


@pytest.fixture
def isolated_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear settings env vars so constructor kwargs are not overridden."""
    for name in _SETTINGS_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def test_settings() -> Settings:
    """Settings pointed at the local docker-compose Postgres instance."""
    return Settings(
        _env_file=None,
        database_url=os.getenv(
            "TEST_DATABASE_URL",
            os.getenv(
                "DATABASE_URL",
                "postgresql://postgres:postgres@localhost:5432/postgres",
            ),
        ),
    )


def _postgres_has_pgvector(settings: Settings) -> bool:
    """Return True when the target database supports the pgvector extension."""
    if not check_connection(settings=settings):
        return False

    try:
        engine = get_engine(settings=settings)
        with engine.begin() as conn:
            # Extension bootstrap only — not an application data path.
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        return True
    except Exception:
        return False


@pytest.fixture
def integration_database_url(test_settings: Settings) -> str:
    """Skip integration tests when Postgres with pgvector is unavailable."""
    if not _postgres_has_pgvector(test_settings):
        pytest.skip(
            "PostgreSQL with pgvector is not available "
            "(start docker compose relational_db or set TEST_DATABASE_URL)"
        )
    return test_settings.database_url
