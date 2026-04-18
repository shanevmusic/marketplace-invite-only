"""Production environment-variable pre-flight check.

Run before booting in production to fail fast on missing or insecure
configuration.  Exits with status 0 if everything required is set and
status 1 otherwise, printing a concise summary of what's missing.

Usage:
    python -m app.scripts.check_env

Intended callers:
- CI: fails a deploy workflow early if a secret was not wired
- ECS task: can be a lightweight init-container command before the main
  gunicorn process starts.
"""

from __future__ import annotations

import os
import sys

# (var_name, human description, required-in-prod?, must-not-equal-literal)
REQUIRED_IN_PROD: list[tuple[str, str, bool, str | None]] = [
    ("APP_ENVIRONMENT", "runtime environment (must be 'prod')", True, None),
    ("APP_DATABASE_URL", "async Postgres URL", True, None),
    ("APP_DATABASE_URL_SYNC", "sync Postgres URL (alembic)", True, None),
    ("APP_JWT_SECRET_PRIMARY", "primary JWT signing key", True, "change_me_phase_3"),
    ("APP_CORS_ORIGINS", "comma-separated allowed origins", True, ""),
    ("APP_S3_BUCKET", "S3 uploads bucket name", True, ""),
    ("APP_S3_REGION", "S3 region", True, ""),
    ("APP_S3_CDN_BASE_URL", "CDN base URL for image serving", False, ""),
    ("APP_FCM_SERVER_KEY", "FCM push key", False, ""),
    ("APP_APNS_KEY_PEM", "APNs p8 key contents", False, ""),
    ("APP_SENTRY_DSN", "Sentry DSN", False, ""),
    ("APP_METRICS_TOKEN", "shared secret for /metrics", False, ""),
]


def main() -> int:
    env = os.environ.get("APP_ENVIRONMENT", "dev")
    if env != "prod":
        print(f"[check_env] skipping: APP_ENVIRONMENT={env} (not prod)")
        return 0

    missing: list[str] = []
    warnings: list[str] = []
    for var, desc, required, bad_literal in REQUIRED_IN_PROD:
        val = os.environ.get(var, "")
        if not val:
            (missing if required else warnings).append(f"  - {var}: {desc}")
        elif bad_literal is not None and val == bad_literal:
            missing.append(f"  - {var}: has insecure default value ({desc})")

    if warnings:
        print("[check_env] WARNING — optional vars not set:")
        for line in warnings:
            print(line)

    if missing:
        print("[check_env] FAIL — required vars missing or insecure:")
        for line in missing:
            print(line)
        return 1

    print("[check_env] OK — all required production env vars present")
    return 0


if __name__ == "__main__":
    sys.exit(main())
