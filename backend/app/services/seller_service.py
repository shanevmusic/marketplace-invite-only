"""Seller service — seller profile lookups + dashboard aggregates.

The dashboard reads lifetime metrics **directly from
``order_analytics_snapshots``** rather than the ``seller_sales_rollups``
materialized view.  Rationale (see ADR-0010 + docs/phase-4-notes.md):

1. The snapshot table is append-only with **no foreign keys** (deliberate,
   Phase 2) so it survives product soft-delete and order hard-delete.
2. Reading the snapshot table directly gives strictly-correct numbers
   without depending on the MV being fresh.  The MV remains useful as a
   pre-aggregated cache for admin cross-seller reports in later phases.

Active-order count is computed live from ``orders`` using the set of
non-terminal statuses.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import SellerNotFound, SellerProfileMissing, VisibilityDenied
from app.models.order import Order
from app.models.order_analytics_snapshot import OrderAnalyticsSnapshot
from app.models.platform_settings import PlatformSettings
from app.models.seller import Seller
from app.models.store import Store
from app.models.user import User


# Orders in these statuses are active / not yet terminal.
# ``completed``, ``cancelled``, and ``delivered`` are considered terminal
# for the active count (delivery finished; retention/analytics handle the rest).
ACTIVE_ORDER_STATUSES: tuple[str, ...] = (
    "pending",
    "accepted",
    "preparing",
    "out_for_delivery",
)


async def get_caller_seller(db: AsyncSession, caller: User) -> Seller:
    """Return the Seller row for the caller or raise 400."""
    result = await db.execute(
        sa.select(Seller).where(
            Seller.user_id == caller.id,
            Seller.deleted_at.is_(None),
        )
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise SellerProfileMissing()
    return seller


async def get_seller_for_caller(
    db: AsyncSession,
    caller: User,
    seller_id: uuid.UUID,
) -> Seller:
    """Fetch a seller applying visibility rules.

    admin: any.
    seller: own only (else 404 to avoid leaking existence).
    customer: only their direct referring seller (ADR-0007, depth=1).
    driver / other: 404.
    """
    result = await db.execute(
        sa.select(Seller).where(
            Seller.id == seller_id,
            Seller.deleted_at.is_(None),
        )
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise SellerNotFound()

    if caller.role == "admin":
        return seller
    if caller.role == "seller":
        if seller.user_id != caller.id:
            raise SellerNotFound()
        return seller
    if caller.role == "customer":
        # Allow if the seller has a public store.
        public_store = await db.execute(
            sa.select(Store.id).where(
                Store.seller_id == seller.id,
                Store.is_public.is_(True),
                Store.deleted_at.is_(None),
            )
        )
        if public_store.scalar_one_or_none() is not None:
            return seller
        if (
            caller.referring_seller_id is None
            or caller.referring_seller_id != seller.id
        ):
            raise VisibilityDenied()
        return seller
    raise SellerNotFound()


async def _get_platform_currency(db: AsyncSession) -> str:
    result = await db.execute(
        sa.select(PlatformSettings.currency_code).where(PlatformSettings.id == 1)
    )
    code = result.scalar_one_or_none()
    return code or "USD"


async def get_dashboard(
    db: AsyncSession,
    caller: User,
    *,
    target_seller_id: Optional[uuid.UUID] = None,
) -> dict:
    """Build the seller dashboard payload.

    If ``target_seller_id`` is provided, only admins may view another
    seller's dashboard; otherwise the caller's own seller row is used.
    """
    if target_seller_id is not None:
        if caller.role != "admin":
            raise VisibilityDenied()
        result = await db.execute(
            sa.select(Seller).where(Seller.id == target_seller_id)
        )
        seller = result.scalar_one_or_none()
        if seller is None:
            raise SellerNotFound()
    else:
        seller = await get_caller_seller(db, caller)

    # Lifetime metrics from append-only snapshot table (survives deletions).
    totals = await db.execute(
        sa.select(
            sa.func.coalesce(
                sa.func.sum(OrderAnalyticsSnapshot.total_minor), 0
            ).label("lifetime_sales_amount"),
            sa.func.count(OrderAnalyticsSnapshot.id).label("lifetime_orders_count"),
        ).where(OrderAnalyticsSnapshot.seller_id == seller.id)
    )
    row = totals.one()
    lifetime_sales = int(row.lifetime_sales_amount or 0)
    lifetime_orders = int(row.lifetime_orders_count or 0)

    active_result = await db.execute(
        sa.select(sa.func.count(Order.id)).where(
            Order.seller_id == seller.id,
            Order.deleted_at.is_(None),
            Order.status.in_(ACTIVE_ORDER_STATUSES),
        )
    )
    active_count = int(active_result.scalar_one() or 0)

    currency = await _get_platform_currency(db)

    return {
        "seller_id": seller.id,
        "lifetime_sales_amount": lifetime_sales,
        "lifetime_orders_count": lifetime_orders,
        "active_orders_count": active_count,
        "currency_code": currency,
        "last_updated": datetime.now(timezone.utc),
    }
