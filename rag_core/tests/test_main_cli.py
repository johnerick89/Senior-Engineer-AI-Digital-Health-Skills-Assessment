"""Tests for python -m rag_core CLI."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rag_core.__main__ import cmd_ingest, cmd_migrate, main
from rag_core.rag.ingestion import IngestResult
import uuid


def test_cmd_migrate_ready() -> None:
    with (
        patch("rag_core.__main__.initialize_vector_store") as mock_init,
        patch("rag_core.__main__.vector_store_is_ready", return_value=True),
    ):
        cmd_migrate()
    mock_init.assert_called_once()


def test_cmd_migrate_not_ready_exits() -> None:
    with (
        patch("rag_core.__main__.initialize_vector_store"),
        patch("rag_core.__main__.vector_store_is_ready", return_value=False),
        pytest.raises(SystemExit, match="migration failed"),
    ):
        cmd_migrate()


def test_cmd_ingest_missing_file(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="File not found"):
        cmd_ingest(tmp_path / "missing.pdf")


def test_cmd_ingest_ok(tmp_path: Path) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF")
    with patch(
        "rag_core.rag.ingestion.ingest_pdf",
        return_value=IngestResult(
            document_id=uuid.uuid4(),
            filename="doc.pdf",
            chunk_count=2,
        ),
    ) as mock_ingest:
        cmd_ingest(pdf)
    mock_ingest.assert_called_once()


def test_main_default_migrate() -> None:
    with patch("rag_core.__main__.cmd_migrate") as mock_migrate:
        main([])
    mock_migrate.assert_called_once()


def test_main_ingest_subcommand(tmp_path: Path) -> None:
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(b"%PDF")
    with patch("rag_core.__main__.cmd_ingest") as mock_ingest:
        main(["ingest", str(pdf)])
    mock_ingest.assert_called_once()
