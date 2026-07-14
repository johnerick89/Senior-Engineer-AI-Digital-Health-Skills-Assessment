"""Database engine and session management."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import Engine, create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from rag_core.core.config import Settings, get_settings
from rag_core.db.migrate import sqlalchemy_url

_engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def configure_engine(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> Engine:
    """Create or replace the global engine and session factory."""
    global _engine, SessionLocal

    resolved = sqlalchemy_url(
        database_url or (settings or get_settings()).database_url
    )

    if _engine is not None:
        _engine.dispose()

    _engine = create_engine(resolved, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine


def get_engine(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> Engine:
    """Return the configured database engine, creating it on first use."""
    if _engine is None or database_url is not None or settings is not None:
        configure_engine(database_url, settings=settings)
    assert _engine is not None
    return _engine


def get_session(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> Session:
    """Open a new Session bound to the configured engine."""
    if SessionLocal is None or database_url is not None or settings is not None:
        configure_engine(database_url, settings=settings)
    assert SessionLocal is not None
    return SessionLocal()


def session_scope(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> Generator[Session, None, None]:
    """Yield a session that closes when the caller finishes."""
    session = get_session(database_url, settings=settings)
    try:
        yield session
    finally:
        session.close()


def check_connection(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> bool:
    """Return True when the database accepts a connection."""
    try:
        engine = get_engine(database_url, settings=settings)
        with Session(engine) as session:
            session.scalar(select(1))
        return True
    except Exception:
        return False
