from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    APP_NAME: str = "CodeReview Agent"
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/codereview"

    # Cache
    REDIS_URL: str = "redis://localhost:6379"

    # GitHub App credentials
    GITHUB_WEBHOOK_SECRET: str = ""
    GITHUB_APP_ID: str = ""
    GITHUB_PRIVATE_KEY: str = ""  # PEM-encoded private key

    # AI — provider selection
    GROQ_API_KEY: str = ""
    AI_PROVIDER: Literal["groq", "nvidia", "anthropic"] = "groq"

    # AI — model & review limits
    # Configurable without code changes — switch between:
    #   openai/gpt-oss-120b  |  llama-3.3-70b-versatile  |  qwen/qwen3-32b
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    AI_MAX_FILES: int = 20                      # max files to review per PR
    AI_MAX_PATCH_CHARS_PER_FILE: int = 12_000   # truncate large patches
    AI_MIN_CONFIDENCE: float = 0.65             # findings below this are filtered out

    # Worker — job execution limits
    REVIEW_JOB_TIMEOUT_SECONDS: int = 300      # per-job wall-clock cap (asyncio.wait_for)

    # GitHub review submission
    # True  → build payload, store in Redis, do NOT call GitHub API (default / safe)
    # False → build payload, store in Redis, AND post to GitHub API
    GITHUB_DRY_RUN: bool = True

    # API authentication
    # API_AUTH_ENABLED: explicitly enable bearer-token auth.
    #   In production, auth is always enforced regardless of this setting.
    # API_AUTH_TOKEN: the secret token clients must send in Authorization: Bearer <token>.
    API_AUTH_ENABLED: bool = False
    API_AUTH_TOKEN: str = ""

    # CORS
    # BACKEND_CORS_ORIGINS: comma-separated list of allowed frontend origins.
    #   Development default: localhost:3000 / 127.0.0.1:3000 are always added.
    #   Production: MUST be set explicitly; startup raises if empty.
    # ALLOW_CREDENTIALS: set False if you do not need cookie / session auth.
    BACKEND_CORS_ORIGINS: list[str] = []
    ALLOW_CREDENTIALS: bool = True

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors_origins(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return list(v)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
