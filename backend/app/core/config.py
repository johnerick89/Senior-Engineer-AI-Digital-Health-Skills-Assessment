"""Environment-backed settings for the FastAPI backend."""

from functools import lru_cache
from typing import Self

from pydantic import AliasChoices, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the backend API."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_env: str = "development"
    log_level: str = "INFO"
    frontend_url: str | None = Field(
        default=None,
        validation_alias=AliasChoices("FRONTEND_URL", "frontend_url"),
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
        if isinstance(v, list):
            return [
                str(origin).strip()
                for origin in v
                if origin is not None and str(origin).strip()
            ]
        return v

    @model_validator(mode="after")
    def append_frontend_origin(self) -> Self:
        """Add FRONTEND_URL to CORS when set and not already listed."""
        if not self.frontend_url:
            return self
        url = self.frontend_url.strip()
        if url and url not in self.allowed_origins:
            self.allowed_origins = [*self.allowed_origins, url]
        return self

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
