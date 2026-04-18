"""Application configuration loaded from environment variables (prefix: APP_).

Reads from a `.env` file if present (python-dotenv), then from the real
environment.  Export a module-level `settings` singleton so every module does:

    from app.core.config import settings
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------
    # Core
    # ------------------------------------------------------------------
    environment: Literal["dev", "test", "prod"] = Field(
        default="dev",
        description="Runtime environment.  Controls log level, debug mode, etc.",
    )

    # ------------------------------------------------------------------
    # Database
    # ------------------------------------------------------------------
    database_url: str = Field(
        default="postgresql+asyncpg://marketplace:marketplace@localhost:5432/marketplace",
        description=(
            "Async SQLAlchemy URL used by the FastAPI application at runtime."
        ),
    )
    database_url_sync: str = Field(
        default="postgresql://marketplace:marketplace@localhost:5432/marketplace",
        description=(
            "Synchronous SQLAlchemy URL used exclusively by Alembic for "
            "schema migrations."
        ),
    )

    # ------------------------------------------------------------------
    # JWT / Auth  (Phase 3 — placeholder values kept stable here)
    # ------------------------------------------------------------------
    jwt_secret: str = Field(
        default="change_me_phase_3",
        description=(
            "Secret key for signing JWT access tokens.  Must be replaced with "
            "a strong random value in staging/production."
        ),
    )
    jwt_algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm.",
    )
    jwt_access_token_expire_minutes: int = Field(
        default=15,
        description="Access-token TTL in minutes.",
    )
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh-token TTL in days.",
    )


# Module-level singleton — import this everywhere.
settings = Settings()
