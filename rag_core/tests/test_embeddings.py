"""Tests for rag_core.embeddings.embed_texts."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from rag_core.embeddings import EMBEDDING_DIMENSION, EMBEDDING_MODEL, embed_texts


def test_embedding_model_is_pinned() -> None:
    assert EMBEDDING_MODEL == "text-embedding-3-small"


def test_embedding_dimension_matches_openai_small_model() -> None:
    assert EMBEDDING_DIMENSION == 1536


def _fake_embedding(index: int, dim: int = EMBEDDING_DIMENSION) -> MagicMock:
    item = MagicMock()
    item.index = index
    item.embedding = [float(index)] * dim
    return item


@patch("rag_core.embeddings.get_async_client")
def test_embed_texts_empty_list(mock_get_client: MagicMock) -> None:
    assert embed_texts([]) == []
    mock_get_client.assert_not_called()


@patch("rag_core.embeddings.get_settings")
@patch("rag_core.embeddings.get_async_client")
def test_embed_texts_batches_and_returns_vectors(
    mock_get_client: MagicMock,
    mock_get_settings: MagicMock,
) -> None:
    mock_get_settings.return_value = MagicMock(ingestion_batch_size=2)
    client = MagicMock()
    response = MagicMock()
    response.data = [_fake_embedding(1), _fake_embedding(0)]  # out of order on purpose
    client.embeddings.create = AsyncMock(return_value=response)
    mock_get_client.return_value = client

    vectors = embed_texts(["a", "b"])

    client.embeddings.create.assert_awaited_once_with(
        model=EMBEDDING_MODEL,
        input=["a", "b"],
    )
    assert len(vectors) == 2
    assert vectors[0][0] == 0.0  # sorted by index
    assert vectors[1][0] == 1.0
    assert all(len(v) == EMBEDDING_DIMENSION for v in vectors)


@patch("rag_core.embeddings.get_settings")
@patch("rag_core.embeddings.get_async_client")
def test_embed_texts_rejects_wrong_dimension(
    mock_get_client: MagicMock,
    mock_get_settings: MagicMock,
) -> None:
    mock_get_settings.return_value = MagicMock(ingestion_batch_size=100)
    client = MagicMock()
    response = MagicMock()
    response.data = [_fake_embedding(0, dim=8)]
    client.embeddings.create = AsyncMock(return_value=response)
    mock_get_client.return_value = client

    with pytest.raises(ValueError, match="Expected embedding dimension"):
        embed_texts(["bad"])
