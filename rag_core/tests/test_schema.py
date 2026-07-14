"""Tests for rag_core.db.schema."""

import pytest

from rag_core.db.schema import (
    CHAT_MESSAGES_TABLE,
    CHAT_THREADS_TABLE,
    DOCUMENT_CHUNKS_TABLE,
    DOCUMENTS_TABLE,
    apply_schema,
    get_schema_ddl,
)


def test_get_schema_ddl_includes_core_tables_and_pgvector() -> None:
    ddl = get_schema_ddl(1536)

    assert "CREATE EXTENSION IF NOT EXISTS vector" in ddl
    assert DOCUMENTS_TABLE in ddl
    assert DOCUMENT_CHUNKS_TABLE in ddl
    assert CHAT_THREADS_TABLE in ddl
    assert CHAT_MESSAGES_TABLE in ddl


def test_get_schema_ddl_uses_embedding_dimension_in_vector_column() -> None:
    ddl = get_schema_ddl(3072)

    assert "vector(3072)" in ddl
    assert "vector(1536)" not in ddl


def test_get_schema_ddl_uses_cosine_index_for_embeddings() -> None:
    ddl = get_schema_ddl(1536)

    assert "USING hnsw (embedding vector_cosine_ops)" in ddl


def test_get_schema_ddl_rejects_invalid_dimension() -> None:
    with pytest.raises(ValueError, match="embedding_dimension must be positive"):
        get_schema_ddl(0)


def test_apply_schema_executes_generated_ddl() -> None:
    executed: list[str] = []

    class FakeConnection:
        def execute(self, sql: str) -> None:
            executed.append(sql)

    apply_schema(FakeConnection(), 1536)

    assert executed == [get_schema_ddl(1536)]
