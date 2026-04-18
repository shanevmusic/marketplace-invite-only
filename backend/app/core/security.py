"""Security utilities: password hashing, JWT creation/verification, refresh tokens.

Design decisions (ADR-0006):
- Access tokens: JWT HS256, 15-min TTL, claims sub/role/jti/exp/iat.
- Refresh tokens: opaque 32-byte URL-safe base64 strings; SHA-256 hash stored.
- Password hashing: Argon2id via argon2-cffi.
"""

from __future__ import annotations

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt

from app.core.config import settings
from app.core.exceptions import InvalidTokenError, TokenExpired

# ---------------------------------------------------------------------------
# Argon2id password hasher — sane OWASP-recommended parameters.
# ---------------------------------------------------------------------------
_ph = PasswordHasher(
    time_cost=2,       # iterations
    memory_cost=65536,  # 64 MiB
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


def hash_password(password: str) -> str:
    """Hash *password* with Argon2id. Returns the encoded hash string."""
    return _ph.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if *password* matches *password_hash*, False otherwise.

    Never raises on mismatches — only returns False.
    """
    try:
        return _ph.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Return True if *password_hash* was produced with weaker argon2 params.

    Used to transparently upgrade older hashes on successful login.
    """
    try:
        return _ph.check_needs_rehash(password_hash)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# ---------------------------------------------------------------------------
# JWT access tokens
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccessTokenPayload:
    """Decoded, validated JWT payload."""

    sub: str        # user_id as string
    role: str
    jti: str
    exp: datetime
    iat: datetime


def create_access_token(user_id: uuid.UUID, role: str) -> tuple[str, datetime]:
    """Create a signed JWT access token.

    Returns ``(encoded_token, expiry_datetime)``.
    """
    now = datetime.now(timezone.utc)
    exp = now + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    jti = secrets.token_hex(16)
    payload: dict[str, object] = {
        "sub": str(user_id),
        "role": role,
        "jti": jti,
        "exp": exp,
        "iat": now,
    }
    token = jwt.encode(
        payload, settings.jwt_signing_key, algorithm=settings.jwt_algorithm
    )
    return token, exp


def decode_access_token(token: str) -> AccessTokenPayload:
    """Decode and validate a JWT access token.

    Raises:
        TokenExpired: if the token's ``exp`` claim is in the past.
        InvalidTokenError: if the token is malformed or the signature is invalid.
    """
    last_exc: JWTError | None = None
    payload = None
    for key in settings.jwt_verification_keys:
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[settings.jwt_algorithm],
            )
            last_exc = None
            break
        except JWTError as exc:
            last_exc = exc
            msg = str(exc).lower()
            # If the token is definitively expired, stop trying other keys.
            if "expired" in msg:
                raise TokenExpired() from exc
            continue
    if payload is None:
        assert last_exc is not None
        raise InvalidTokenError() from last_exc

    try:
        return AccessTokenPayload(
            sub=payload["sub"],
            role=payload["role"],
            jti=payload["jti"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
            iat=datetime.fromtimestamp(payload["iat"], tz=timezone.utc),
        )
    except (KeyError, TypeError) as exc:
        raise InvalidTokenError("Token payload is malformed.") from exc


# ---------------------------------------------------------------------------
# Refresh tokens — opaque random strings; only SHA-256 hash stored.
# ---------------------------------------------------------------------------


def generate_refresh_token() -> tuple[str, str]:
    """Generate a new refresh token.

    Returns ``(plaintext, sha256_hex_hash)``.  The plaintext is sent to the
    client; only the hash is persisted.
    """
    plaintext = secrets.token_urlsafe(32)
    token_hash = hash_refresh_token(plaintext)
    return plaintext, token_hash


def hash_refresh_token(plaintext: str) -> str:
    """Return the SHA-256 hex digest of *plaintext*."""
    return hashlib.sha256(plaintext.encode()).hexdigest()
