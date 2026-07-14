"""Tests for Alembic models / migrate helpers."""

from unittest.mock import MagicMock, patch

from rag_core.db.base import Base
from rag_core.db.migrate import get_alembic_config, run_migrations, sqlalchemy_url
from rag_core.models import ChatMessage, Document, DocumentChunk
from rag_core.rag.embeddings import EMBEDDING_DIMENSION


def test_sqlalchemy_url_uses_psycopg_dialect() -> None:
    assert (
        sqlalchemy_url("postgresql://postgres:postgres@localhost:5432/postgres")
        == "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
    )


def test_models_registered_on_metadata() -> None:
    # Import side effect via models package
    import rag_core.models  # noqa: F401

    table_names = set(Base.metadata.tables)
    assert {
        "documents",
        "document_chunks",
        "chat_threads",
        "chat_messages",
        "usage_events",
    }.issubset(table_names)


def test_document_chunk_embedding_dimension() -> None:
    col = DocumentChunk.__table__.c.embedding
    assert col.type.dim == EMBEDDING_DIMENSION


def test_document_and_message_are_model_classes() -> None:
    assert Document.__tablename__ == "documents"
    assert ChatMessage.__tablename__ == "chat_messages"


@patch("rag_core.db.migrate._stamp_if_legacy_schema_present")
@patch("rag_core.db.migrate.command.upgrade")
def test_run_migrations_calls_alembic_upgrade(
    mock_upgrade: MagicMock,
    _mock_stamp: MagicMock,
) -> None:
    run_migrations("postgresql://postgres:postgres@localhost:5432/postgres")
    mock_upgrade.assert_called_once()
    cfg = mock_upgrade.call_args.args[0]
    assert (
        cfg.get_main_option("sqlalchemy.url")
        == "postgresql+psycopg://postgres:postgres@localhost:5432/postgres"
    )


def test_get_alembic_config_sets_script_location() -> None:
    cfg = get_alembic_config("postgresql://example/db")
    assert "alembic" in cfg.get_main_option("script_location")
