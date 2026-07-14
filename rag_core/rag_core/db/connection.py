"""PostgreSQL connection helpers."""

from typing import Any

import psycopg
from psycopg import Connection

from rag_core.core.config import Settings, get_settings


def connect(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
    **connect_kwargs: Any,
) -> Connection:
    """Open a psycopg connection using settings or an explicit URL."""
    url = database_url or (settings or get_settings()).database_url
    return psycopg.connect(url, **connect_kwargs)


def check_connection(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
) -> bool:
    """Return True when the database accepts a connection."""
    try:
        with connect(database_url, settings=settings) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False
