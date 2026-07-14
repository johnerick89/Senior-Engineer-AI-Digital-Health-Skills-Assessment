"""Alembic migration helpers."""

from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from rag_core.core.config import Settings, get_settings

_RAG_CORE_ROOT = Path(__file__).resolve().parents[2]
_ALEMBIC_INI = _RAG_CORE_ROOT / "alembic.ini"
_INITIAL_REVISION = "0001_initial_rag_schema"


def sqlalchemy_url(database_url: str) -> str:
    """Convert a libpq/psycopg URL to the SQLAlchemy psycopg3 dialect URL."""
    if database_url.startswith("postgresql+psycopg://"):
        return database_url
    if database_url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql+asyncpg://")
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgresql://")
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    return database_url


def get_alembic_config(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> Config:
    """Build an Alembic Config pointed at this package's alembic.ini."""
    resolved = sqlalchemy_url(database_url or (settings or get_settings()).database_url)
    cfg = Config(str(_ALEMBIC_INI))
    cfg.set_main_option("sqlalchemy.url", resolved)
    cfg.set_main_option("script_location", str(_RAG_CORE_ROOT / "alembic"))
    return cfg


def _stamp_if_legacy_schema_present(cfg: Config) -> None:
    """Stamp the initial revision when tables already exist from pre-Alembic DDL.

    Older runs used ``apply_schema()`` without ``alembic_version``. Stamping
    avoids DuplicateTable errors on the first ``upgrade``.
    """
    url = cfg.get_main_option("sqlalchemy.url")
    engine = create_engine(url)
    with engine.connect() as conn:
        documents_exists = conn.execute(
            text("SELECT to_regclass('public.documents') IS NOT NULL")
        ).scalar()
        version_exists = conn.execute(
            text("SELECT to_regclass('public.alembic_version') IS NOT NULL")
        ).scalar()
    engine.dispose()

    if documents_exists and not version_exists:
        command.stamp(cfg, _INITIAL_REVISION)


def run_migrations(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
    revision: str = "head",
) -> None:
    """Apply Alembic migrations up to ``revision`` (default: head)."""
    cfg = get_alembic_config(database_url, settings=settings)
    _stamp_if_legacy_schema_present(cfg)
    command.upgrade(cfg, revision)
