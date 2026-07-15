"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """FastAPI TestClient with vector-store init mocked out."""
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/postgres",
    )
    with patch("rag_core.rag.vector_store.initialize_vector_store"):
        from app.main import app

        with TestClient(app) as test_client:
            yield test_client
