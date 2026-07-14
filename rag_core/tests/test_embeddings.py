"""Tests for rag_core.embeddings constants."""

from rag_core.embeddings import EMBEDDING_DIMENSION, EMBEDDING_MODEL


def test_embedding_model_is_pinned() -> None:
    assert EMBEDDING_MODEL == "text-embedding-3-small"


def test_embedding_dimension_matches_openai_small_model() -> None:
    assert EMBEDDING_DIMENSION == 1536
