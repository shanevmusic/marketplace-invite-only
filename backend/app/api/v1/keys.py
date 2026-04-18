"""Public-key registry endpoints (Phase 6, ADR-0009, ADR-0013)."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.rate_limiter import limiter
from app.models.user import User
from app.models.user_public_key import UserPublicKey
from app.schemas.keys import (
    PublicKeyListResponse,
    PublicKeyResponse,
    RegisterKeyRequest,
    encode_public_key_b64url,
)
from app.services import key_service, messaging_service


router = APIRouter(prefix="/keys", tags=["keys"])


def _render(row: UserPublicKey) -> PublicKeyResponse:
    return PublicKeyResponse(
        key_id=row.id,
        user_id=row.user_id,
        public_key_b64url=encode_public_key_b64url(bytes(row.public_key)),
        key_version=row.key_version,
        status=row.status,
        created_at=row.created_at,
        rotated_at=row.rotated_at,
        revoked_at=row.revoked_at,
    )


@router.post("", response_model=PublicKeyResponse, status_code=201)
@limiter.limit("10/minute")
async def register_key(
    request: Request,
    body: RegisterKeyRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> PublicKeyResponse:
    """Register (or rotate to) a new active X25519 public key for the caller."""
    row = await key_service.register_key(
        db,
        user=caller,
        public_key_raw=body.to_bytes(),
        key_version=body.key_version,
    )
    return _render(row)


@router.get("/me", response_model=PublicKeyListResponse)
async def list_my_keys(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> PublicKeyListResponse:
    """List all of the caller's keys (active + rotated + revoked)."""
    rows = await key_service.list_keys_for_user(db, caller.id)
    return PublicKeyListResponse(data=[_render(r) for r in rows])


@router.get("/{user_id}", response_model=PublicKeyResponse)
async def get_user_active_key(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> PublicKeyResponse:
    """Fetch a user's current active public key.

    Respects conversation eligibility (ADR-0013): callers can only fetch
    keys of users they are allowed to message.  Otherwise 404.
    """
    if caller.id != user_id:
        # pylint: disable=protected-access
        can = await messaging_service._can_converse(
            db, caller=caller, peer_id=user_id
        )
        if not can:
            from app.core.exceptions import PublicKeyNotFound

            raise PublicKeyNotFound()
    row = await key_service.get_active_key_for_user(db, user_id)
    return _render(row)


@router.delete("/{key_id}", status_code=204)
@limiter.limit("10/minute")
async def revoke_key(
    request: Request,
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_user),
) -> Response:
    """Revoke one of the caller's own keys."""
    await key_service.revoke_key(db, caller=caller, key_id=key_id)
    return Response(status_code=204)
