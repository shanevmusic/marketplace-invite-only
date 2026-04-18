"""User public-key service (Phase 6, ADR-0009, ADR-0013).

Handles X25519 public key registration, rotation (atomic mark-old-rotated
+ insert-new-active), listing, and revocation.

Keys are 32-byte raw bytes on the DB; the REST surface uses base64url.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import KeyOwnershipError, PublicKeyNotFound
from app.models.user import User
from app.models.user_public_key import UserPublicKey


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def register_key(
    db: AsyncSession,
    *,
    user: User,
    public_key_raw: bytes,
    key_version: int,
) -> UserPublicKey:
    """Register a new active key for the user.

    Atomically:
    1. Lock all of the user's current ACTIVE rows `FOR UPDATE`.
    2. Mark them `status='rotated'` with `rotated_at=now()`.
    3. Flush (so the partial unique index releases the active slot).
    4. Insert the new ACTIVE row.
    """
    now = _now()

    existing = await db.execute(
        sa.select(UserPublicKey)
        .where(
            UserPublicKey.user_id == user.id,
            UserPublicKey.status == "active",
        )
        .with_for_update()
    )
    for old in existing.scalars().all():
        old.status = "rotated"
        old.rotated_at = now
    await db.flush()

    new_row = UserPublicKey(
        id=uuid.uuid4(),
        user_id=user.id,
        public_key=public_key_raw,
        key_version=key_version,
        status="active",
        registered_at=now,
        created_at=now,
    )
    db.add(new_row)
    await db.flush()
    return new_row


async def get_active_key_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> UserPublicKey:
    """Return the one active key for the given user or raise."""
    result = await db.execute(
        sa.select(UserPublicKey).where(
            UserPublicKey.user_id == user_id,
            UserPublicKey.status == "active",
        )
    )
    row = result.scalar_one_or_none()
    if row is None:
        raise PublicKeyNotFound()
    return row


async def list_keys_for_user(
    db: AsyncSession, user_id: uuid.UUID
) -> list[UserPublicKey]:
    result = await db.execute(
        sa.select(UserPublicKey)
        .where(UserPublicKey.user_id == user_id)
        .order_by(UserPublicKey.created_at.desc())
    )
    return list(result.scalars().all())


async def revoke_key(
    db: AsyncSession, *, caller: User, key_id: uuid.UUID
) -> UserPublicKey:
    """Revoke caller's own key.  Non-owners get a 404 (no existence leak)."""
    result = await db.execute(
        sa.select(UserPublicKey)
        .where(UserPublicKey.id == key_id)
        .with_for_update()
    )
    row = result.scalar_one_or_none()
    if row is None or row.user_id != caller.id:
        raise KeyOwnershipError()
    if row.status != "revoked":
        row.status = "revoked"
        row.revoked_at = _now()
    await db.flush()
    return row
