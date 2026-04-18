"""Pydantic schemas for the public-key registry.

All keys are 32-byte raw X25519 public keys, transported as base64url strings.
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _decode_b64url_32(v: str) -> bytes:
    """Decode a base64url string and assert the output is exactly 32 bytes."""
    if not isinstance(v, str):
        raise ValueError("public_key_b64url must be a string")
    # Accept with or without padding
    try:
        padded = v + "=" * (-len(v) % 4)
        raw = base64.urlsafe_b64decode(padded.encode("ascii"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"public_key_b64url is not valid base64url: {exc}") from exc
    if len(raw) != 32:
        raise ValueError(
            f"public_key_b64url must decode to 32 bytes, got {len(raw)}"
        )
    return raw


class RegisterKeyRequest(BaseModel):
    """Body for ``POST /keys``."""

    model_config = ConfigDict(extra="forbid")

    public_key_b64url: str = Field(..., min_length=1, max_length=128)
    key_version: int = Field(default=1, ge=1)

    @field_validator("public_key_b64url")
    @classmethod
    def _validate_key(cls, v: str) -> str:
        _decode_b64url_32(v)
        return v

    def to_bytes(self) -> bytes:
        return _decode_b64url_32(self.public_key_b64url)


class PublicKeyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key_id: uuid.UUID
    user_id: uuid.UUID
    public_key_b64url: str
    key_version: int
    status: str
    created_at: datetime
    rotated_at: datetime | None = None
    revoked_at: datetime | None = None


class PublicKeyListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[PublicKeyResponse]


def encode_public_key_b64url(raw: bytes) -> str:
    """Encode 32 bytes → URL-safe base64 without padding."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
