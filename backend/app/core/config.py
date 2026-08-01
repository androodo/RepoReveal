"""Centralized application settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "RepoReveal"
    environment: str = "development"
    debug: bool = False
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:3000"

    database_url: str = "postgresql+asyncpg://reporeveal:reporeveal@localhost:5432/reporeveal"

    github_token: str | None = None
    github_api_base_url: str = "https://api.github.com"
    github_api_version: str = "2022-11-28"
    github_timeout_seconds: float = 30.0

    openai_api_key: str | None = None
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    ai_enabled: bool = True
    ai_max_context_chars: int = 24_000
    ai_max_retrieved_chunks: int = 12
    openai_timeout_seconds: float = 60.0
    openai_max_retries: int = 2
    embedding_dimensions: int = 1536

    max_archive_bytes: int = 50 * 1024 * 1024
    max_extracted_bytes: int = 150 * 1024 * 1024
    max_extracted_files: int = 5_000
    max_python_files: int = 2_000
    max_single_file_bytes: int = 1 * 1024 * 1024
    analysis_timeout_seconds: int = 300

    temp_dir: str = "/tmp/reporeveal"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def ai_available(self) -> bool:
        return bool(self.ai_enabled and self.openai_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
