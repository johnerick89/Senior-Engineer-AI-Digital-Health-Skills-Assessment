"""CLI entrypoint for rag_core maintenance tasks.

Usage:
  python -m rag_core              # migrate + readiness check
  python -m rag_core migrate      # alembic upgrade head
  python -m rag_core ingest FILE  # ingest a PDF
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rag_core.core.logging import configure_logging, get_logger
from rag_core.vector_store import initialize_vector_store, vector_store_is_ready

logger = get_logger(__name__)


def cmd_migrate() -> None:
    """Apply Alembic migrations and report readiness."""
    initialize_vector_store()
    if vector_store_is_ready():
        print("rag_core vector store migrated and ready")
    else:
        raise SystemExit("rag_core vector store migration failed")


def cmd_ingest(pdf_path: Path) -> None:
    """Ingest a single PDF into the vector store."""
    from rag_core.ingestion import ingest_pdf

    if not pdf_path.is_file():
        raise SystemExit(f"File not found: {pdf_path}")

    result = ingest_pdf(pdf_path, filename=pdf_path.name)
    print(
        f"ingested document_id={result.document_id} "
        f"chunks={result.chunk_count} filename={result.filename}"
    )


def main(argv: list[str] | None = None) -> None:
    configure_logging()
    parser = argparse.ArgumentParser(prog="python -m rag_core")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("migrate", help="Run Alembic migrations (default)")
    ingest_parser = sub.add_parser("ingest", help="Ingest a PDF file")
    ingest_parser.add_argument("pdf_path", type=Path, help="Path to a .pdf file")

    args = parser.parse_args(argv)

    if args.command in (None, "migrate"):
        cmd_migrate()
    elif args.command == "ingest":
        cmd_ingest(args.pdf_path)
    else:
        parser.print_help()
        sys.exit(2)


if __name__ == "__main__":
    main()
