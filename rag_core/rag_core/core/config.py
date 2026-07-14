"""Environment-backed settings for rag_core."""

from functools import lru_cache

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for rag_core.

    Only settings that are genuinely environment-specific or safe to tune
    without a data migration live here. The embedding model, its dimension,
    and the pgvector distance metric are intentionally NOT here — they are
    pinned as constants in ``embeddings.py`` / ``vector_store.py``, since
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

    # PostgreSQL + pgvector (sync psycopg). Compose overrides host to relational_db.
    database_url: str = Field(
        default="postgresql://postgres:postgres@localhost:5432/postgres",
        alias="DATABASE_URL",
        description="PostgreSQL connection URL for pgvector storage.",
    )

    openai_api_key: str = Field(
        default="",
        alias="OPENAI_API_KEY",
        description="OpenAI API key for embeddings and generation.",
    )

    # Chat/generation model. Safe to override per environment — unlike the
    # embedding model, swapping this doesn't require re-processing stored data.
    generation_model: str = Field(
        default="gpt-4o-mini",
        validation_alias=AliasChoices(
            "RAG_CORE_GENERATION_MODEL",
            "RAG_CORE_MODEL",
            "generation_model",
        ),
        description="Chat completion model identifier.",
    )

    # Retrieval / ingestion tuning.
    retrieval_k: int = Field(
        default=10,
        validation_alias=AliasChoices("RAG_CORE_RETRIEVAL_K", "retrieval_k"),
        description="Number of chunks to retrieve per query.",
    )
    ingestion_batch_size: int = Field(
        default=100,
        validation_alias=AliasChoices(
            "RAG_CORE_INGESTION_BATCH_SIZE",
            "ingestion_batch_size",
        ),
        description="Batch size for document ingestion operations.",
    )

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
