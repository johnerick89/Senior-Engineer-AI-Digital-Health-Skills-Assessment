"""pgvector store initialization and health checks."""

from psycopg import Connection

from rag_core.core.config import Settings, get_settings
from rag_core.db.connection import check_connection, connect
from rag_core.db.schema import apply_schema
from rag_core.embeddings import EMBEDDING_DIMENSION
from pgvector.psycopg import register_vector


def initialize_vector_store(
    database_url: str | None = None,
    *,
    settings: Settings | None = None,
    embedding_dimension: int | None = None,
) -> None:
    """Create pgvector extension and core tables if they do not exist."""
    resolved_settings = settings or get_settings()
    dimension = embedding_dimension or EMBEDDING_DIMENSION
    url = database_url or resolved_settings.database_url

    with connect(url, settings=resolved_settings) as conn:
        apply_schema(conn, dimension)
        register_vector(conn)
        conn.commit()


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

    required_tables = ("documents", "document_chunks", "chat_threads", "chat_messages")
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = ANY(%s)
    """

    try:
        with connect(url, settings=resolved_settings) as conn:
            rows = conn.execute(query, (list(required_tables),)).fetchall()
        return {row[0] for row in rows} == set(required_tables)
    except Exception:
        return False


def register_vector_adapter(conn: Connection) -> None:
    """Register pgvector type adapters on a psycopg connection."""
    register_vector(conn)
