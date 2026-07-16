"""Environment-backed settings for rag_core."""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for rag_core.

    Only settings that are genuinely environment-specific or safe to tune
    without a data migration live here. The embedding model, its dimension,
    and the pgvector distance metric are intentionally NOT here — they are
    pinned as constants in ``rag.embeddings`` / ``rag.vector_store``, since
    changing them requires re-embedding existing data, not a config toggle.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = "development"
    log_level: str = "INFO"

    # CORS — frontend (and Chainlit, if it ever calls the backend directly).
    allowed_origins: list[str] | str = [
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    # Per-step wall-clock timeout in seconds.
    agent_step_timeout_seconds: int = Field(
        default=120,
        validation_alias=AliasChoices(
            "RAG_CORE_STEP_TIMEOUT_SECONDS",
            "agent_step_timeout_seconds",
        ),
        description="Timeout for a single OpenAI / agent step.",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()


settings = get_settings()
