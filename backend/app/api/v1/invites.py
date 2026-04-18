"""Invites router.

Endpoints:
    GET  /invites/validate?token=...  — public
    POST /invites/admin               — admin only
    POST /invites/seller_referral     — seller (or admin)
    POST /invites/seller_referral/regenerate — seller (or admin)
    GET  /invites                     — seller or admin
    DELETE /invites/{id}              — admin any; seller own

Rate limits:
    POST /invites/*: 20/min per user
    GET  /invites/validate: 30/min per IP
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_admin,
    get_current_seller_or_admin,
    get_current_user,
    get_db,
)
from app.models.user import User
from app.schemas.invites import (
    CreateAdminInviteRequest,
    InviteListResponse,
    InviteResponse,
    ValidateInviteResponse,
)
from app.services import invite_service
from app.core.rate_limiter import limiter

router = APIRouter(prefix="/invites", tags=["invites"])


# ---------------------------------------------------------------------------
# GET /invites/validate?token=...  — public
# ---------------------------------------------------------------------------


@router.get("/validate", response_model=ValidateInviteResponse)
@limiter.limit("30/minute")
async def validate_invite(
    request: Request,
    token: str,
    db: AsyncSession = Depends(get_db),
) -> ValidateInviteResponse:
    """Public endpoint: validate an invite token without consuming it."""
    return await invite_service.validate_invite(db, token)


# ---------------------------------------------------------------------------
# POST /invites/admin — admin only
# ---------------------------------------------------------------------------


@router.post("/admin", response_model=InviteResponse, status_code=201)
@limiter.limit("20/minute")
async def create_admin_invite(
    request: Request,
    body: CreateAdminInviteRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_admin),
) -> InviteResponse:
    """Create a single-use admin invite for any role. Admin only."""
    invite, plaintext = await invite_service.create_admin_invite(
        db,
        issuer=user,
        role_target=body.role_target,
        expires_in_hours=body.expires_in_hours,
        email_hint=body.email_hint,
    )
    return invite_service._build_invite_response(invite, token_plaintext=plaintext)


# ---------------------------------------------------------------------------
# POST /invites/seller_referral — seller or admin
# ---------------------------------------------------------------------------


@router.post("/seller_referral", response_model=InviteResponse, status_code=201)
@limiter.limit("20/minute")
async def get_or_create_seller_referral(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_seller_or_admin),
) -> InviteResponse:
    """Return active seller referral or create one. Idempotent."""
    invite, plaintext = await invite_service.get_or_create_seller_referral(db, user)
    return invite_service._build_invite_response(invite, token_plaintext=plaintext)


# ---------------------------------------------------------------------------
# POST /invites/seller_referral/regenerate — seller or admin
# ---------------------------------------------------------------------------


@router.post("/seller_referral/regenerate", response_model=InviteResponse, status_code=201)
@limiter.limit("20/minute")
async def regenerate_seller_referral(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_seller_or_admin),
) -> InviteResponse:
    """Revoke current seller referral and issue a new one."""
    invite, plaintext = await invite_service.regenerate_seller_referral(db, user)
    return invite_service._build_invite_response(invite, token_plaintext=plaintext)


# ---------------------------------------------------------------------------
# GET /invites — seller or admin (own)
# ---------------------------------------------------------------------------


@router.get("", response_model=InviteListResponse)
async def list_invites(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_seller_or_admin),
) -> InviteListResponse:
    """List invites issued by the caller."""
    invites = await invite_service.list_own_invites(db, user)
    data = [invite_service._build_invite_response(inv) for inv in invites]
    return InviteListResponse(
        data=data,
        pagination={"next_cursor": None, "has_more": False},
    )


# ---------------------------------------------------------------------------
# DELETE /invites/{id} — admin any; seller own
# ---------------------------------------------------------------------------


@router.delete("/{invite_id}", status_code=204)
async def revoke_invite(
    invite_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Revoke an invite. Admin: any. Seller: only own seller_referral."""
    await invite_service.revoke_invite(db, user, invite_id)
    return Response(status_code=204)
