"""DDL for pgvector-backed document chunks and chat history."""

from psycopg import Connection

DOCUMENTS_TABLE = "documents"
DOCUMENT_CHUNKS_TABLE = "document_chunks"
CHAT_THREADS_TABLE = "chat_threads"
CHAT_MESSAGES_TABLE = "chat_messages"
USAGE_EVENTS_TABLE = "usage_events"


def get_schema_ddl(embedding_dimension: int) -> str:
    """Return SQL that enables pgvector and creates core RAG tables."""
    if embedding_dimension <= 0:
        raise ValueError("embedding_dimension must be positive")

    return f"""
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS {DOCUMENTS_TABLE} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'processing',
    size_bytes INTEGER,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {DOCUMENT_CHUNKS_TABLE} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES {DOCUMENTS_TABLE}(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    page_number INTEGER,
    embedding vector({embedding_dimension}),
    prompt_tokens INTEGER,
    estimated_cost_usd NUMERIC(12, 8),
    model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index)
);

CREATE TABLE IF NOT EXISTS {CHAT_THREADS_TABLE} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS {CHAT_MESSAGES_TABLE} (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id UUID NOT NULL REFERENCES {CHAT_THREADS_TABLE}(id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER,
    estimated_cost_usd NUMERIC(12, 8),
    model TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS usage_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    kind TEXT NOT NULL CHECK (kind IN (
        'suggestion', 'chat_completion', 'query_embedding', 'ingest_embedding'
    )),
    model TEXT,
    prompt_tokens INTEGER NOT NULL DEFAULT 0,
    completion_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost_usd NUMERIC(12, 8) NOT NULL DEFAULT 0,
    thread_id UUID REFERENCES {CHAT_THREADS_TABLE}(id) ON DELETE SET NULL,
    message_id UUID REFERENCES {CHAT_MESSAGES_TABLE}(id) ON DELETE SET NULL,
    document_id UUID REFERENCES {DOCUMENTS_TABLE}(id) ON DELETE SET NULL,
    chunk_id UUID REFERENCES {DOCUMENT_CHUNKS_TABLE}(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_document_chunks_document_id
    ON {DOCUMENT_CHUNKS_TABLE} (document_id);

CREATE INDEX IF NOT EXISTS ix_chat_messages_thread_id_created_at
    ON {CHAT_MESSAGES_TABLE} (thread_id, created_at);

CREATE INDEX IF NOT EXISTS ix_usage_events_kind ON usage_events (kind);

CREATE INDEX IF NOT EXISTS ix_document_chunks_embedding_hnsw
    ON {DOCUMENT_CHUNKS_TABLE}
    USING hnsw (embedding vector_cosine_ops);
"""


def apply_schema(conn: Connection, embedding_dimension: int) -> None:
    """Apply pgvector schema DDL on the provided connection."""
    conn.execute(get_schema_ddl(embedding_dimension))
