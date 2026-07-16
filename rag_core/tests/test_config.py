"""Tests for rag_core.core.config."""

import pytest

from rag_core.core.config import Settings, get_settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()
    settings = Settings(_env_file=None)

    assert settings.database_url.startswith("postgresql://")
    assert "asyncpg" not in settings.database_url
    assert settings.generation_model == "gpt-4o-mini"
    assert settings.retrieval_k == 20
    assert settings.ingestion_batch_size == 100
    assert settings.agent_step_timeout_seconds == 120
    assert settings.app_env == "development"
    assert settings.log_level == "INFO"
    assert "http://localhost:3000" in settings.allowed_origins


def test_settings_override_from_explicit_values(isolated_settings_env: None) -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:pass@db:5432/rag",
        generation_model="gpt-4o",
        retrieval_k=5,
        ingestion_batch_size=50,
        openai_api_key="test-key",
        agent_step_timeout_seconds=30,
    )

    assert settings.database_url == "postgresql://user:pass@db:5432/rag"
    assert settings.generation_model == "gpt-4o"
    assert settings.retrieval_k == 5
    assert settings.ingestion_batch_size == 50
    assert settings.openai_api_key == "test-key"
    assert settings.agent_step_timeout_seconds == 30


def test_settings_does_not_expose_embedding_toggles(isolated_settings_env: None) -> None:
    settings = Settings(_env_file=None)
    assert not hasattr(settings, "embedding_model")
    assert not hasattr(settings, "embedding_dimension")


def test_allowed_origins_parses_comma_separated_string(
    isolated_settings_env: None,
) -> None:
    settings = Settings(
        _env_file=None,
        allowed_origins="http://a.example, http://b.example,",
    )
    assert settings.allowed_origins == ["http://a.example", "http://b.example"]


def test_generation_model_from_rag_core_generation_model_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAG_CORE_MODEL", raising=False)
    monkeypatch.setenv("RAG_CORE_GENERATION_MODEL", "gpt-4o")
    settings = Settings(_env_file=None)
    assert settings.generation_model == "gpt-4o"


def test_generation_model_accepts_legacy_rag_core_model_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("RAG_CORE_GENERATION_MODEL", raising=False)
    monkeypatch.setenv("RAG_CORE_MODEL", "gpt-4o")
    settings = Settings(_env_file=None)
    assert settings.generation_model == "gpt-4o"


def test_get_settings_is_cached() -> None:
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second
