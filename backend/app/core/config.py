"""Application configuration loaded from environment variables (prefix: APP_).

Reads from a `.env` file if present (python-dotenv), then from the real
environment.  Export a module-level `settings` singleton so every module does:

    from app.core.config import settings

Security contract for jwt_secret:
- In "prod" environment: startup raises RuntimeError if the secret equals
  the insecure default value.  This is an intentional hard-fail safeguard.
- In "dev" or "test" environment: a warning is logged instead so that local
  development and CI continue to work without requiring a secret.
"""

from __future__ import annotations

import logging
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_logger = logging.getLogger(__name__)

_INSECURE_JWT_DEFAULT = "change_me_phase_3"


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
        default=_INSECURE_JWT_DEFAULT,
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

    # ------------------------------------------------------------------
    # Startup secret validation
    # ------------------------------------------------------------------

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        """Hard-fail if the insecure default JWT secret is used outside dev/test."""
        if self.jwt_secret == _INSECURE_JWT_DEFAULT:
            if self.environment in ("dev", "test"):
                _logger.warning(
                    "APP_JWT_SECRET is set to the insecure default value "
                    "'%s'.  This is only acceptable in dev/test environments. "
                    "Set a strong random secret before deploying to production.",
                    _INSECURE_JWT_DEFAULT,
                )
            else:
                raise RuntimeError(
                    "APP_JWT_SECRET must not equal the insecure default value "
                    f"'{_INSECURE_JWT_DEFAULT}' in environment '{self.environment}'. "
                    "Set APP_JWT_SECRET to a strong random value before starting "
                    "the application in production."
                )
        return self


# Module-level singleton — import this everywhere.
settings = Settings()
