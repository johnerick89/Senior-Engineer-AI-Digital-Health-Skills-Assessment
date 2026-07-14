"""CLI entrypoint for rag_core maintenance tasks."""

from rag_core.vector_store import initialize_vector_store, vector_store_is_ready


def main() -> None:
    """Initialize the pgvector schema and report readiness."""
    initialize_vector_store()
    if vector_store_is_ready():
        print("rag_core vector store initialized and ready")
    else:
        raise SystemExit("rag_core vector store initialization failed")


if __name__ == "__main__":
    main()
