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
            "a strong random value in staging/production.  Deprecated alias "
            "for APP_JWT_SECRET_PRIMARY; kept for backwards compatibility."
        ),
    )
    jwt_secret_primary: str = Field(
        default="",
        description=(
            "Primary JWT signing secret.  When set, overrides APP_JWT_SECRET. "
            "New tokens are signed with this key."
        ),
    )
    jwt_secret_secondary: str = Field(
        default="",
        description=(
            "Fallback JWT verification secret used during rotation.  Tokens "
            "minted with the previous primary remain valid until they expire."
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
    # CORS
    # ------------------------------------------------------------------
    cors_origins: str = Field(
        default="",
        description=(
            "Comma-separated list of allowed origins for CORS.  Empty means "
            "deny-all in prod; dev/test default to '*' via code fallback."
        ),
    )

    # ------------------------------------------------------------------
    # Object storage (S3) — optional, Phase 12 (B-G1)
    # ------------------------------------------------------------------
    s3_bucket: str = Field(default="", description="S3 bucket name.")
    s3_region: str = Field(default="us-east-1", description="S3 region.")
    aws_access_key_id: str = Field(default="", description="AWS access key.")
    aws_secret_access_key: str = Field(default="", description="AWS secret.")
    s3_cdn_base_url: str = Field(
        default="",
        description="CDN base URL prefixing final image URLs, no trailing slash.",
    )
    s3_upload_max_bytes: int = Field(
        default=10 * 1024 * 1024,
        description="Max allowed size for object-storage uploads (bytes).",
    )
    s3_presign_expires_seconds: int = Field(
        default=300,
        description="Expiry window for presigned upload URLs.",
    )

    # ------------------------------------------------------------------
    # Push notifications (FCM / APNs) — optional, Phase 12 (f)
    # ------------------------------------------------------------------
    fcm_server_key: str = Field(default="", description="FCM legacy server key.")
    apns_key_id: str = Field(default="", description="APNs auth key ID.")
    apns_team_id: str = Field(default="", description="APNs team ID.")
    apns_bundle_id: str = Field(default="", description="APNs bundle ID.")
    apns_key_pem: str = Field(default="", description="APNs p8 auth key PEM contents.")

    # ------------------------------------------------------------------
    # Observability — Sentry + Prometheus (Phase 13)
    # ------------------------------------------------------------------
    sentry_dsn: str = Field(
        default="",
        description="Sentry DSN.  Empty disables Sentry initialisation.",
    )
    sentry_release: str = Field(
        default="",
        description="Release identifier sent to Sentry (git SHA or version).",
    )
    metrics_token: str = Field(
        default="",
        description=(
            "Shared secret required in X-Metrics-Token header to access "
            "/metrics.  Empty disables the endpoint entirely (returns 404)."
        ),
    )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def jwt_signing_key(self) -> str:
        """Return the secret used to SIGN new tokens."""
        return self.jwt_secret_primary or self.jwt_secret

    @property
    def jwt_verification_keys(self) -> list[str]:
        """Return the ordered list of secrets accepted for verification."""
        keys: list[str] = []
        seen: set[str] = set()
        for candidate in (
            self.jwt_secret_primary,
            self.jwt_secret,
            self.jwt_secret_secondary,
        ):
            if candidate and candidate not in seen:
                keys.append(candidate)
                seen.add(candidate)
        if not keys:
            keys.append(self.jwt_secret)
        return keys

    @property
    def cors_origins_list(self) -> list[str]:
        """Return parsed CORS origins.

        In dev/test, an empty env falls back to '*' to keep local workflows
        frictionless.  In prod, empty means deny-all.
        """
        raw = [o.strip() for o in self.cors_origins.split(",") if o.strip()]
        if raw:
            return raw
        if self.environment in ("dev", "test"):
            return ["*"]
        return []

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
