"""Operational helper for JWT secret rotation (Phase 12).

Prints a fresh random secret plus the exact steps operators should follow
to roll the primary/secondary pair without invalidating in-flight tokens.

The script intentionally does NOT mutate any file — rotation is a deploy
operation gated on operator judgement.  Run via:

    python -m app.scripts.rotate_jwt_secret
"""

from __future__ import annotations

import secrets


def main() -> None:
    new_secret = secrets.token_urlsafe(48)
    print("Generated new JWT secret (store in a secrets manager):\n")
    print(f"  {new_secret}\n")
    print("Rotation procedure:")
    print("  1. Set APP_JWT_SECRET_SECONDARY = <current APP_JWT_SECRET_PRIMARY>")
    print("  2. Set APP_JWT_SECRET_PRIMARY   = <new secret above>")
    print("  3. Redeploy the backend.  Existing access tokens remain valid")
    print("     until they expire (APP_JWT_ACCESS_TOKEN_EXPIRE_MINUTES).")
    print("  4. After the expiry window, unset APP_JWT_SECRET_SECONDARY.")


if __name__ == "__main__":
    main()
