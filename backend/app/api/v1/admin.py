"""Phase 11 admin endpoints — users, content, analytics, ops.

All endpoints require ``role='admin'``.  Existing admin features
(message retention, order purge) live in ``admin_messages`` /
``admin_orders``; this module adds the Phase 11 admin panel surface.
"""

from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_db
from app.core.exceptions import NotFoundError
from app.core.rate_limiter import limiter
from app.models.user import User
from app.schemas.admin import (
    AdminAnalyticsOverview,
    AdminIssueInviteRequest,
    AdminIssueInviteResponse,
    AdminProductListResponse,
    AdminProductSummary,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserSummary,
    DisableProductRequest,
    MigrationVersionResponse,
    ReferralEdge,
    SuspendUserRequest,
    TopSellerEntry,
    TopSellersResponse,
)
from app.schemas.conversations import (
    MessageRetentionResponse,
    PurgeMessagesResponse,
    UpdateMessageRetentionRequest,
)
from app.services import admin_service, messaging_service


router = APIRouter(prefix="/admin", tags=["admin"])


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


@router.get("/users", response_model=AdminUserListResponse)
async def list_users(
    q: Optional[str] = Query(default=None, max_length=200),
    role: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminUserListResponse:
    rows, next_cursor = await admin_service.list_users(
        db, q=q, role=role, status=status, cursor=cursor, limit=limit
    )
    return AdminUserListResponse(
        data=[AdminUserSummary.model_validate(u) for u in rows],
        pagination={"next_cursor": next_cursor, "has_more": next_cursor is not None},
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
async def get_user_detail(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminUserDetail:
    user, ref_by, ref_users = await admin_service.get_user_detail(db, user_id)

    # Resolve referrer/referred users for display.
    edge_ids: set[uuid.UUID] = set()
    if ref_by is not None:
        edge_ids.add(ref_by.referrer_id)
    edge_ids.update(r.referred_user_id for r in ref_users)

    users_by_id: dict[uuid.UUID, User] = {}
    if edge_ids:
        import sqlalchemy as sa

        rows = (
            await db.execute(sa.select(User).where(User.id.in_(edge_ids)))
        ).scalars().all()
        users_by_id = {u.id: u for u in rows}

    referred_by = None
    if ref_by is not None:
        u = users_by_id.get(ref_by.referrer_id)
        if u is not None:
            referred_by = ReferralEdge(
                user_id=u.id,
                email=u.email,
                display_name=u.display_name,
                role=u.role,
                created_at=ref_by.created_at,
            )

    referred_users: list[ReferralEdge] = []
    for r in ref_users:
        u = users_by_id.get(r.referred_user_id)
        if u is None:
            continue
        referred_users.append(
            ReferralEdge(
                user_id=u.id,
                email=u.email,
                display_name=u.display_name,
                role=u.role,
                created_at=r.created_at,
            )
        )

    base = AdminUserSummary.model_validate(user).model_dump()
    return AdminUserDetail(
        **base,
        referred_by=referred_by,
        referred_users=referred_users,
    )


@router.post("/users/{user_id}/suspend", response_model=AdminUserSummary)
@limiter.limit("30/minute")
async def suspend_user(
    request: Request,
    user_id: uuid.UUID,
    body: SuspendUserRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminUserSummary:
    user = await admin_service.suspend_user(db, user_id, reason=body.reason)
    return AdminUserSummary.model_validate(user)


@router.post("/users/{user_id}/unsuspend", response_model=AdminUserSummary)
@limiter.limit("30/minute")
async def unsuspend_user(
    request: Request,
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminUserSummary:
    user = await admin_service.unsuspend_user(db, user_id)
    return AdminUserSummary.model_validate(user)


# ---------------------------------------------------------------------------
# Invites (admin override)
# ---------------------------------------------------------------------------


@router.post(
    "/invites",
    response_model=AdminIssueInviteResponse,
    status_code=201,
)
@limiter.limit("20/minute")
async def issue_invite(
    request: Request,
    body: AdminIssueInviteRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminIssueInviteResponse:
    invite, plaintext = await admin_service.issue_admin_invite(
        db,
        issuer=caller,
        role_target=body.role_target,
        expires_in_days=body.expires_in_days,
    )
    return AdminIssueInviteResponse(
        id=invite.id,
        token=plaintext,
        role_target=invite.role_target,
        expires_at=invite.expires_at,
        created_at=invite.created_at,
    )


# ---------------------------------------------------------------------------
# Products (content moderation)
# ---------------------------------------------------------------------------


@router.get("/products", response_model=AdminProductListResponse)
async def list_products(
    q: Optional[str] = Query(default=None, max_length=200),
    status: Optional[str] = Query(default=None),
    seller_id: Optional[uuid.UUID] = Query(default=None),
    cursor: Optional[str] = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminProductListResponse:
    rows, next_cursor = await admin_service.list_products(
        db, q=q, status=status, seller_id=seller_id, cursor=cursor, limit=limit
    )
    return AdminProductListResponse(
        data=[AdminProductSummary.model_validate(p) for p in rows],
        pagination={"next_cursor": next_cursor, "has_more": next_cursor is not None},
    )


@router.post(
    "/products/{product_id}/disable", response_model=AdminProductSummary
)
@limiter.limit("30/minute")
async def disable_product(
    request: Request,
    product_id: uuid.UUID,
    body: DisableProductRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminProductSummary:
    product = await admin_service.disable_product(
        db, product_id, reason=body.reason
    )
    return AdminProductSummary.model_validate(product)


@router.post(
    "/products/{product_id}/restore", response_model=AdminProductSummary
)
@limiter.limit("30/minute")
async def restore_product(
    request: Request,
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminProductSummary:
    product = await admin_service.restore_product(db, product_id)
    return AdminProductSummary.model_validate(product)


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


@router.get("/analytics/overview", response_model=AdminAnalyticsOverview)
async def analytics_overview(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> AdminAnalyticsOverview:
    data = await admin_service.get_analytics_overview(db)
    return AdminAnalyticsOverview(**data)


@router.get("/analytics/top-sellers", response_model=TopSellersResponse)
async def analytics_top_sellers(
    limit: int = Query(default=10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> TopSellersResponse:
    rows = await admin_service.get_top_sellers(db, limit=limit)
    return TopSellersResponse(
        data=[TopSellerEntry(**r) for r in rows]
    )


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------


@router.get(
    "/ops/retention-config", response_model=MessageRetentionResponse
)
async def ops_get_retention(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> MessageRetentionResponse:
    days = await messaging_service.get_message_retention_days(db)
    return MessageRetentionResponse(message_retention_days=days)


@router.post(
    "/ops/retention-config", response_model=MessageRetentionResponse
)
@limiter.limit("30/minute")
async def ops_set_retention(
    request: Request,
    body: UpdateMessageRetentionRequest,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> MessageRetentionResponse:
    days = await messaging_service.update_message_retention_days(
        db, caller=caller, days=body.message_retention_days
    )
    return MessageRetentionResponse(message_retention_days=days)


@router.post("/ops/purge-messages/run", response_model=PurgeMessagesResponse)
@limiter.limit("6/minute")
async def ops_run_purge(
    request: Request,
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> PurgeMessagesResponse:
    count = await messaging_service.purge_old_messages(db)
    return PurgeMessagesResponse(purged_count=count)


@router.get(
    "/ops/migration-version", response_model=MigrationVersionResponse
)
async def ops_migration_version(
    db: AsyncSession = Depends(get_db),
    caller: User = Depends(get_current_admin),
) -> MigrationVersionResponse:
    version = await admin_service.get_migration_version(db)
    return MigrationVersionResponse(version=version)
