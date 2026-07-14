"""pgvector store initialization and health checks.

Schema creation is owned by Alembic (`rag_core.db.migrate.run_migrations`).
"""

from sqlalchemy import inspect

from rag_core.core.config import Settings, get_settings
from rag_core.db.migrate import run_migrations
from rag_core.db.session import check_connection, configure_engine, get_engine


def initialize_vector_store(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
    embedding_dimension: int | None = None,
) -> None:
    """Run Alembic migrations and refresh the SQLAlchemy engine."""
    _ = embedding_dimension  # dimension is pinned in models / migration
    resolved_settings = settings or get_settings()
    url = database_url or resolved_settings.database_url

    run_migrations(url, settings=resolved_settings)
    configure_engine(url, settings=resolved_settings)


def vector_store_is_ready(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> bool:
    """Return True when the database is reachable and core tables exist."""
    resolved_settings = settings or get_settings()
    url = database_url or resolved_settings.database_url

    if not check_connection(url, settings=resolved_settings):
        return False

    required_tables = {
        "documents",
        "document_chunks",
        "chat_threads",
        "chat_messages",
        "usage_events",
    }
    try:
        engine = get_engine(url, settings=resolved_settings)
        existing = set(inspect(engine).get_table_names())
        return required_tables.issubset(existing)
    except Exception:
        return False
