"""Admin service — Phase 11.

Thin data-access helpers for the admin panel.  Business rules:
- Admin-only callers (router enforces via ``get_current_admin``).
- Suspension sets ``users.status='suspended'``; account becomes inaccessible on
  the next request (``get_current_user`` rejects suspended accounts).
- Disable sets ``products.status='disabled'`` (admin override) without
  touching ``is_active``.  Listing code still checks ``is_active`` for
  seller-driven visibility; ``status='disabled'`` is additionally hidden.
- Admin-issued invites bypass the seller-referral requirement (ADR-0002).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.invite_link import InviteLink
from app.models.order_analytics_snapshot import OrderAnalyticsSnapshot
from app.models.product import Product
from app.models.referral import Referral
from app.models.seller import Seller
from app.models.user import User


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

VALID_ROLES = {"admin", "seller", "customer", "driver"}
VALID_STATUS = {"active", "suspended"}


async def list_users(
    db: AsyncSession,
    *,
    q: Optional[str] = None,
    role: Optional[str] = None,
    status: Optional[str] = None,
    cursor: Optional[str] = None,
    limit: int = 25,
) -> tuple[list[User], Optional[str]]:
    """Paginated user list.  Cursor is the last row's ``created_at.isoformat()``.

    Returns ``(rows, next_cursor)``.  ``next_cursor is None`` when exhausted.
    """
    limit = max(1, min(limit, 100))
    stmt = sa.select(User).where(User.deleted_at.is_(None))
    if q:
        ilike = f"%{q}%"
        stmt = stmt.where(
            sa.or_(User.email.ilike(ilike), User.display_name.ilike(ilike))
        )
    if role and role in VALID_ROLES:
        stmt = stmt.where(User.role == role)
    if status and status in VALID_STATUS:
        stmt = stmt.where(User.status == status)
    if cursor:
        try:
            ts = datetime.fromisoformat(cursor)
            stmt = stmt.where(User.created_at < ts)
        except ValueError:
            pass
    stmt = stmt.order_by(User.created_at.desc()).limit(limit + 1)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].created_at.isoformat() if has_more and rows else None
    return rows, next_cursor


async def get_user_detail(
    db: AsyncSession, user_id: uuid.UUID
) -> tuple[User, Optional[Referral], list[Referral]]:
    """Return ``(user, referred_by_edge, referred_users_edges)``."""
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("User not found.")

    rb_stmt = sa.select(Referral).where(Referral.referred_user_id == user_id)
    referred_by = (await db.execute(rb_stmt)).scalar_one_or_none()

    ru_stmt = sa.select(Referral).where(Referral.referrer_id == user_id)
    referred_users = list((await db.execute(ru_stmt)).scalars().all())

    return user, referred_by, referred_users


async def suspend_user(
    db: AsyncSession, user_id: uuid.UUID, reason: str
) -> User:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("User not found.")
    user.status = "suspended"
    user.suspended_at = datetime.now(timezone.utc)
    user.suspended_reason = reason
    await db.flush()
    await db.refresh(user)
    return user


async def unsuspend_user(db: AsyncSession, user_id: uuid.UUID) -> User:
    user = await db.get(User, user_id)
    if user is None or user.deleted_at is not None:
        raise NotFoundError("User not found.")
    user.status = "active"
    user.suspended_at = None
    user.suspended_reason = None
    await db.flush()
    await db.refresh(user)
    return user


# ---------------------------------------------------------------------------
# Invites (admin override)
# ---------------------------------------------------------------------------


async def issue_admin_invite(
    db: AsyncSession,
    *,
    issuer: User,
    role_target: str,
    expires_in_days: int,
) -> tuple[InviteLink, str]:
    """Admin override: single-use invite bypassing seller-referral requirement."""
    import secrets

    if role_target not in VALID_ROLES:
        raise NotFoundError(f"Invalid role_target: {role_target!r}")

    plaintext = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)
    invite = InviteLink(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        type="admin_invite",
        token=plaintext,
        role_target=role_target,
        max_uses=1,
        used_count=0,
        expires_at=expires_at,
    )
    db.add(invite)
    await db.flush()
    await db.refresh(invite)
    return invite, plaintext


# ---------------------------------------------------------------------------
# Products
# ---------------------------------------------------------------------------


async def list_products(
    db: AsyncSession,
    *,
    q: Optional[str] = None,
    status: Optional[str] = None,
    seller_id: Optional[uuid.UUID] = None,
    cursor: Optional[str] = None,
    limit: int = 25,
) -> tuple[list[Product], Optional[str]]:
    limit = max(1, min(limit, 100))
    stmt = sa.select(Product).where(Product.deleted_at.is_(None))
    if q:
        stmt = stmt.where(Product.name.ilike(f"%{q}%"))
    if status in {"active", "disabled", "out_of_stock"}:
        stmt = stmt.where(Product.status == status)
    if seller_id:
        stmt = stmt.where(Product.seller_id == seller_id)
    if cursor:
        try:
            ts = datetime.fromisoformat(cursor)
            stmt = stmt.where(Product.created_at < ts)
        except ValueError:
            pass
    stmt = stmt.order_by(Product.created_at.desc()).limit(limit + 1)
    result = await db.execute(stmt)
    rows = list(result.scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = rows[-1].created_at.isoformat() if has_more and rows else None
    return rows, next_cursor


async def disable_product(
    db: AsyncSession, product_id: uuid.UUID, reason: str
) -> Product:
    product = await db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise NotFoundError("Product not found.")
    product.status = "disabled"
    product.disabled_at = datetime.now(timezone.utc)
    product.disabled_reason = reason
    await db.flush()
    await db.refresh(product)
    return product


async def restore_product(db: AsyncSession, product_id: uuid.UUID) -> Product:
    product = await db.get(Product, product_id)
    if product is None or product.deleted_at is not None:
        raise NotFoundError("Product not found.")
    product.status = "active"
    product.disabled_at = None
    product.disabled_reason = None
    await db.flush()
    await db.refresh(product)
    return product


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


async def get_analytics_overview(db: AsyncSession) -> dict:
    now = datetime.now(timezone.utc)
    horizon_24h = now - timedelta(hours=24)
    horizon_7d = now - timedelta(days=7)
    horizon_30d = now - timedelta(days=30)

    # GMV + order count from append-only snapshots (survives order purges).
    gmv_row = (
        await db.execute(
            sa.select(
                sa.func.coalesce(sa.func.sum(OrderAnalyticsSnapshot.total_minor), 0),
                sa.func.count(OrderAnalyticsSnapshot.id),
            )
        )
    ).one()
    total_gmv_minor = int(gmv_row[0] or 0)
    orders_count = int(gmv_row[1] or 0)

    # Active users proxy = users created in the window + users with recent orders.
    # Keep it simple: count distinct users who created orders in the window.
    async def _active(horizon: datetime) -> int:
        result = await db.execute(
            sa.select(
                sa.func.count(sa.distinct(OrderAnalyticsSnapshot.customer_id))
            ).where(OrderAnalyticsSnapshot.delivered_at >= horizon)
        )
        return int(result.scalar() or 0)

    active_users_24h = await _active(horizon_24h)
    active_users_7d = await _active(horizon_7d)
    active_users_30d = await _active(horizon_30d)

    # Role counts (exclude soft-deleted).
    role_rows = (
        await db.execute(
            sa.select(User.role, sa.func.count(User.id))
            .where(User.deleted_at.is_(None))
            .group_by(User.role)
        )
    ).all()
    by_role = {r: int(c) for r, c in role_rows}

    return {
        "total_gmv_minor": total_gmv_minor,
        "orders_count": orders_count,
        "active_users_24h": active_users_24h,
        "active_users_7d": active_users_7d,
        "active_users_30d": active_users_30d,
        "seller_count": by_role.get("seller", 0),
        "customer_count": by_role.get("customer", 0),
        "driver_count": by_role.get("driver", 0),
        "admin_count": by_role.get("admin", 0),
    }


async def get_top_sellers(
    db: AsyncSession, limit: int = 10
) -> list[dict]:
    limit = max(1, min(limit, 100))
    # Read directly from the MV; join Seller for display_name.  Fall back to
    # aggregating the snapshot table if the MV is stale/empty.
    try:
        stmt = sa.text(
            """
            SELECT r.seller_id,
                   s.display_name,
                   r.lifetime_revenue_minor,
                   r.lifetime_order_count
            FROM seller_sales_rollups r
            JOIN sellers s ON s.id = r.seller_id
            ORDER BY r.lifetime_revenue_minor DESC
            LIMIT :lim
            """
        ).bindparams(lim=limit)
        rows = (await db.execute(stmt)).all()
        if rows:
            return [
                {
                    "seller_id": r[0],
                    "display_name": r[1],
                    "lifetime_revenue_minor": int(r[2] or 0),
                    "lifetime_order_count": int(r[3] or 0),
                }
                for r in rows
            ]
    except Exception:
        pass

    # Fallback: aggregate snapshots directly.
    stmt = (
        sa.select(
            OrderAnalyticsSnapshot.seller_id,
            sa.func.coalesce(sa.func.sum(OrderAnalyticsSnapshot.total_minor), 0),
            sa.func.count(OrderAnalyticsSnapshot.id),
        )
        .group_by(OrderAnalyticsSnapshot.seller_id)
        .order_by(sa.func.sum(OrderAnalyticsSnapshot.total_minor).desc())
        .limit(limit)
    )
    snap_rows = (await db.execute(stmt)).all()
    if not snap_rows:
        return []
    seller_ids = [r[0] for r in snap_rows]
    sellers = (
        await db.execute(sa.select(Seller).where(Seller.id.in_(seller_ids)))
    ).scalars().all()
    name_by_id = {s.id: s.display_name for s in sellers}
    return [
        {
            "seller_id": r[0],
            "display_name": name_by_id.get(r[0], "Unknown"),
            "lifetime_revenue_minor": int(r[1] or 0),
            "lifetime_order_count": int(r[2] or 0),
        }
        for r in snap_rows
    ]


# ---------------------------------------------------------------------------
# Ops
# ---------------------------------------------------------------------------


async def get_migration_version(db: AsyncSession) -> Optional[str]:
    try:
        result = await db.execute(sa.text("SELECT version_num FROM alembic_version"))
        row = result.first()
        return str(row[0]) if row else None
    except Exception:
        return None
