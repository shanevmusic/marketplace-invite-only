"""Order service — lifecycle, fulfillment, retention, and purge.

All transitions take a row lock (`SELECT ... FOR UPDATE`) on the order
before checking current state and updating.  Stock reservation on
``POST /orders`` similarly locks each product row.

See ADR-0003 (out_for_delivery actors), ADR-0007 (referral visibility),
ADR-0012 (state machine + retention).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Optional

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    DeliveryAlreadyStarted,
    DriverAlreadyAssigned,
    DriverNotRequested,
    FulfillmentAlreadyChosen,
    OrderInvalidTransition,
    OrderNotFound,
    OrderRetentionNotMet,
    ProductNotVisible,
    ProductOutOfStock,
    SellerProfileMissing,
)
from app.models.delivery import Delivery
from app.models.driver_assignment import DriverAssignment
from app.models.order import Order
from app.models.order_analytics_snapshot import OrderAnalyticsSnapshot
from app.models.order_item import OrderItem
from app.models.platform_settings import PlatformSettings
from app.models.product import Product
from app.models.seller import Seller
from app.models.store import Store
from app.models.user import User

# ---------------------------------------------------------------------------
# State-machine definition
# ---------------------------------------------------------------------------

# Statuses in which an order is still "active" (non-terminal, non-delivered).
ACTIVE_STATUSES: frozenset[str] = frozenset(
    {"pending", "accepted", "preparing", "out_for_delivery"}
)

# Terminal states for retention / purge.
TERMINAL_STATUSES: frozenset[str] = frozenset({"completed", "cancelled"})


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _load_order_locked(
    db: AsyncSession, order_id: uuid.UUID
) -> Optional[Order]:
    """Load an order row with ``SELECT ... FOR UPDATE`` (no relationship load)."""
    result = await db.execute(
        sa.select(Order).where(Order.id == order_id).with_for_update()
    )
    return result.scalar_one_or_none()


async def _load_order_full(
    db: AsyncSession, order_id: uuid.UUID
) -> Optional[Order]:
    """Load an order with items, delivery, driver assignments eagerly."""
    result = await db.execute(
        sa.select(Order)
        .options(
            selectinload(Order.order_items),
            selectinload(Order.delivery),
            selectinload(Order.driver_assignments),
        )
        .where(Order.id == order_id)
    )
    return result.scalar_one_or_none()


async def _get_caller_seller(db: AsyncSession, caller: User) -> Seller:
    result = await db.execute(
        sa.select(Seller).where(
            Seller.user_id == caller.id, Seller.deleted_at.is_(None)
        )
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise SellerProfileMissing()
    return seller


def _terminal_at(order: Order) -> Optional[datetime]:
    """Return the earliest terminal timestamp, or None if not terminal."""
    if order.status == "completed":
        return order.completed_at
    if order.status == "cancelled":
        return order.cancelled_at
    return None


def _ensure_can_view(order: Order, caller: User) -> None:
    """Raise OrderNotFound if caller may not see this order."""
    if caller.role == "admin":
        return
    if caller.role == "seller":
        # Compare against sellers.id == users.id invariant (ADR-0011).
        if order.seller_id != caller.id:
            raise OrderNotFound()
        return
    if caller.role == "customer":
        if order.customer_id != caller.id:
            raise OrderNotFound()
        return
    if caller.role == "driver":
        # Driver sees an order only if they're assigned to the delivery or
        # the driver_assignment row.
        delivery = order.delivery
        if delivery is not None and delivery.driver_id == caller.id:
            return
        for assignment in order.driver_assignments:
            if assignment.driver_id == caller.id and assignment.status in (
                "assigned",
                "accepted",
            ):
                return
        raise OrderNotFound()
    raise OrderNotFound()


# ---------------------------------------------------------------------------
# Create order
# ---------------------------------------------------------------------------


async def create_order(
    db: AsyncSession,
    *,
    customer: User,
    items: list[dict[str, Any]],
    delivery_address: dict[str, Any],
) -> Order:
    """Customer places an order.

    - Validates each product is visible to the customer (ADR-0007 depth=1).
    - Locks product rows, verifies stock, decrements atomically.
    - Writes order + line items + computes totals server-side.
    """
    if customer.role != "customer":
        raise ProductNotVisible(
            "Only customers may place orders."
        )
    if not items:
        raise OrderInvalidTransition("Order must have at least one line item.")

    if customer.referring_seller_id is None:
        # Unreferred customers can't see any products — reject immediately.
        raise ProductNotVisible()

    # Lock all product rows up front in id order to avoid deadlocks.
    product_ids = sorted({item["product_id"] for item in items})
    stmt = (
        sa.select(Product)
        .options(selectinload(Product.store))
        .where(Product.id.in_(product_ids))
        .with_for_update()
        .order_by(Product.id)
    )
    result = await db.execute(stmt)
    products = list(result.scalars().all())
    products_by_id = {p.id: p for p in products}

    if len(products_by_id) != len(product_ids):
        raise ProductNotVisible()

    # Aggregate quantities per product (if caller sent duplicates).
    qty_by_id: dict[uuid.UUID, int] = {}
    for item in items:
        qty_by_id[item["product_id"]] = (
            qty_by_id.get(item["product_id"], 0) + int(item["quantity"])
        )

    # All products must belong to the same seller — the customer's
    # referring seller.
    expected_seller_id = customer.referring_seller_id
    seller_ids = {p.seller_id for p in products}
    if len(seller_ids) != 1 or expected_seller_id not in seller_ids:
        raise ProductNotVisible()

    # Visibility + active + stock checks.
    for pid, qty in qty_by_id.items():
        product = products_by_id[pid]
        if product.deleted_at is not None or not product.is_active:
            raise ProductNotVisible()
        if product.stock_quantity is not None and product.stock_quantity < qty:
            raise ProductOutOfStock()

    # Decrement stock (where applicable).
    for pid, qty in qty_by_id.items():
        product = products_by_id[pid]
        if product.stock_quantity is not None:
            product.stock_quantity = product.stock_quantity - qty

    # Determine store (single seller -> single store by Phase 4 rule).
    # Use the store reference from the first product.
    first_product = next(iter(products_by_id.values()))
    store_id = first_product.store_id

    subtotal = sum(
        products_by_id[pid].price_minor * qty for pid, qty in qty_by_id.items()
    )
    total = subtotal  # No fees / tax in Phase 5.

    order_id = uuid.uuid4()
    order = Order(
        id=order_id,
        customer_id=customer.id,
        seller_id=expected_seller_id,
        store_id=store_id,
        status="pending",
        subtotal_minor=subtotal,
        total_minor=total,
        delivery_address=delivery_address,
    )
    db.add(order)
    await db.flush()

    for pid, qty in qty_by_id.items():
        product = products_by_id[pid]
        db.add(
            OrderItem(
                id=uuid.uuid4(),
                order_id=order.id,
                product_id=product.id,
                product_name_snapshot=product.name,
                unit_price_minor_snapshot=product.price_minor,
                quantity=qty,
            )
        )
    await db.flush()

    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


# ---------------------------------------------------------------------------
# State transitions
# ---------------------------------------------------------------------------


async def _lock_order_or_404(
    db: AsyncSession, order_id: uuid.UUID, caller: User
) -> Order:
    order = await _load_order_locked(db, order_id)
    if order is None or order.deleted_at is not None:
        raise OrderNotFound()

    # Seller ownership check (cheap — relies on invariant seller.id == user.id)
    if caller.role == "seller" and order.seller_id != caller.id:
        raise OrderNotFound()
    if caller.role == "customer" and order.customer_id != caller.id:
        raise OrderNotFound()
    # Drivers / admins validated per-endpoint.
    return order


async def accept_order(
    db: AsyncSession, *, caller: User, order_id: uuid.UUID
) -> Order:
    """Seller accepts a pending order."""
    if caller.role != "seller":
        raise OrderNotFound()
    order = await _lock_order_or_404(db, order_id, caller)
    if order.status != "pending":
        raise OrderInvalidTransition(
            f"Cannot accept order in state {order.status!r}."
        )
    order.status = "accepted"
    order.accepted_at = _now()
    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


async def mark_preparing(
    db: AsyncSession, *, caller: User, order_id: uuid.UUID
) -> Order:
    """Seller marks order preparing."""
    if caller.role != "seller":
        raise OrderNotFound()
    order = await _lock_order_or_404(db, order_id, caller)
    if order.status != "accepted":
        raise OrderInvalidTransition(
            f"Cannot transition to preparing from {order.status!r}."
        )
    order.status = "preparing"
    order.preparing_at = _now()
    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


async def choose_self_delivery(
    db: AsyncSession, *, caller: User, order_id: uuid.UUID
) -> Order:
    """Seller chooses self-delivery fulfillment.

    May be called while order is `accepted` or `preparing`.  Second call
    returns 409 FULFILLMENT_ALREADY_CHOSEN.
    """
    if caller.role != "seller":
        raise OrderNotFound()
    order = await _lock_order_or_404(db, order_id, caller)
    if order.status not in ("accepted", "preparing"):
        raise OrderInvalidTransition(
            f"Cannot choose fulfillment in state {order.status!r}."
        )

    # Existing delivery row?  (can't re-choose.)
    existing_delivery = await db.execute(
        sa.select(Delivery).where(Delivery.order_id == order.id)
    )
    if existing_delivery.scalar_one_or_none() is not None:
        raise FulfillmentAlreadyChosen()

    # Or pending driver request?
    existing_req = await db.execute(
        sa.select(DriverAssignment).where(
            DriverAssignment.order_id == order.id,
            DriverAssignment.status.in_(("requested", "assigned", "accepted")),
        )
    )
    if existing_req.scalar_one_or_none() is not None:
        raise FulfillmentAlreadyChosen()

    seller = await _get_caller_seller(db, caller)
    delivery = Delivery(
        id=uuid.uuid4(),
        order_id=order.id,
        driver_id=None,
        seller_id=seller.id,
        status="pending",
    )
    db.add(delivery)
    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


async def request_driver(
    db: AsyncSession, *, caller: User, order_id: uuid.UUID
) -> Order:
    """Seller requests an admin-assigned driver."""
    if caller.role != "seller":
        raise OrderNotFound()
    order = await _lock_order_or_404(db, order_id, caller)
    if order.status not in ("accepted", "preparing"):
        raise OrderInvalidTransition(
            f"Cannot request driver in state {order.status!r}."
        )

    existing_delivery = await db.execute(
        sa.select(Delivery).where(Delivery.order_id == order.id)
    )
    if existing_delivery.scalar_one_or_none() is not None:
        raise FulfillmentAlreadyChosen()

    existing_req = await db.execute(
        sa.select(DriverAssignment).where(
            DriverAssignment.order_id == order.id,
            DriverAssignment.status.in_(("requested", "assigned", "accepted")),
        )
    )
    if existing_req.scalar_one_or_none() is not None:
        raise FulfillmentAlreadyChosen()

    seller = await _get_caller_seller(db, caller)
    assignment = DriverAssignment(
        id=uuid.uuid4(),
        order_id=order.id,
        driver_id=None,
        status="requested",
        requested_by_seller_id=seller.id,
    )
    db.add(assignment)
    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


async def assign_driver(
    db: AsyncSession,
    *,
    caller: User,
    order_id: uuid.UUID,
    driver_id: uuid.UUID,
) -> Order:
    """Admin assigns a driver to a requested order."""
    if caller.role != "admin":
        raise OrderNotFound()
    order = await _lock_order_or_404(db, order_id, caller)
    if order.status not in ("accepted", "preparing"):
        raise OrderInvalidTransition(
            f"Cannot assign driver in state {order.status!r}."
        )

    # Must be a driver user, active.
    drv_result = await db.execute(
        sa.select(User).where(
            User.id == driver_id,
            User.role == "driver",
            User.deleted_at.is_(None),
            User.is_active.is_(True),
        )
    )
    driver_user = drv_result.scalar_one_or_none()
    if driver_user is None:
        raise OrderInvalidTransition("Driver not found or inactive.")

    # Find the requested row.
    req_result = await db.execute(
        sa.select(DriverAssignment)
        .where(DriverAssignment.order_id == order.id)
        .order_by(DriverAssignment.requested_at.desc())
        .with_for_update()
    )
    assignments = list(req_result.scalars().all())
    active = [a for a in assignments if a.status in ("requested", "assigned", "accepted")]
    if not active:
        raise DriverNotRequested()
    # If already assigned
    already_assigned = [a for a in active if a.driver_id is not None]
    if already_assigned:
        raise DriverAlreadyAssigned()

    pending = active[0]
    pending.driver_id = driver_id
    pending.status = "assigned"
    pending.assigned_by_admin_id = caller.id
    pending.assigned_at = _now()
    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


async def out_for_delivery(
    db: AsyncSession, *, caller: User, order_id: uuid.UUID
) -> Order:
    """Transition preparing → out_for_delivery (ADR-0003, idempotent → 409)."""
    if caller.role not in ("seller", "driver"):
        raise OrderNotFound()
    order = await _lock_order_or_404(db, order_id, caller)

    # If we've already transitioned, second call → 409 DELIVERY_ALREADY_STARTED
    if order.status == "out_for_delivery" or order.out_for_delivery_at is not None:
        raise DeliveryAlreadyStarted()

    if order.status != "preparing":
        raise OrderInvalidTransition(
            f"Cannot transition to out_for_delivery from {order.status!r}."
        )

    # Find existing delivery OR a driver assignment.
    del_result = await db.execute(
        sa.select(Delivery).where(Delivery.order_id == order.id).with_for_update()
    )
    delivery = del_result.scalar_one_or_none()

    assigned_driver_id: Optional[uuid.UUID] = None
    if delivery is None:
        # Driver-assigned path: the assignment row has been set by admin.
        assign_result = await db.execute(
            sa.select(DriverAssignment).where(
                DriverAssignment.order_id == order.id,
                DriverAssignment.status.in_(("assigned", "accepted")),
                DriverAssignment.driver_id.is_not(None),
            )
        )
        assignment = assign_result.scalar_one_or_none()
        if assignment is None:
            raise OrderInvalidTransition(
                "No fulfillment mode chosen for this order."
            )
        assigned_driver_id = assignment.driver_id

        # Authority: driver or seller can trigger in driver-assigned mode.
        if caller.role == "driver" and caller.id != assigned_driver_id:
            raise OrderNotFound()
        if caller.role == "seller" and caller.id != order.seller_id:
            raise OrderNotFound()

        # Lazily create deliveries row.
        delivery = Delivery(
            id=uuid.uuid4(),
            order_id=order.id,
            driver_id=assigned_driver_id,
            seller_id=order.seller_id,
            status="in_transit",
            started_at=_now(),
        )
        db.add(delivery)
    else:
        # Self-deliver: only seller can trigger (delivery.driver_id IS NULL).
        # Driver-assigned via pre-existing delivery row: either actor OK.
        if delivery.driver_id is None:
            # Self-deliver
            if caller.role != "seller" or caller.id != order.seller_id:
                raise OrderNotFound()
        else:
            if caller.role == "driver" and caller.id != delivery.driver_id:
                raise OrderNotFound()
            if caller.role == "seller" and caller.id != order.seller_id:
                raise OrderNotFound()
        delivery.status = "in_transit"
        delivery.started_at = _now()

    order.status = "out_for_delivery"
    order.out_for_delivery_at = _now()
    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


async def mark_delivered(
    db: AsyncSession, *, caller: User, order_id: uuid.UUID
) -> Order:
    """Transition out_for_delivery → delivered.  Driver (if assigned) OR seller (self)."""
    if caller.role not in ("seller", "driver"):
        raise OrderNotFound()
    order = await _lock_order_or_404(db, order_id, caller)
    if order.status != "out_for_delivery":
        raise OrderInvalidTransition(
            f"Cannot transition to delivered from {order.status!r}."
        )

    del_result = await db.execute(
        sa.select(Delivery).where(Delivery.order_id == order.id).with_for_update()
    )
    delivery = del_result.scalar_one_or_none()
    if delivery is None:
        raise OrderInvalidTransition("Delivery row missing.")

    if delivery.driver_id is None:
        if caller.role != "seller" or caller.id != order.seller_id:
            raise OrderNotFound()
    else:
        if caller.role == "driver" and caller.id != delivery.driver_id:
            raise OrderNotFound()
        if caller.role == "seller" and caller.id != order.seller_id:
            raise OrderNotFound()

    order.status = "delivered"
    order.delivered_at = _now()
    delivery.status = "delivered"
    delivery.delivered_at = _now()
    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


async def complete_order(
    db: AsyncSession, *, caller: User, order_id: uuid.UUID
) -> Order:
    """Customer confirms receipt; writes analytics snapshot atomically.

    Idempotent at the DB level via ``UNIQUE(order_id)`` + ON CONFLICT.
    """
    if caller.role != "customer":
        raise OrderNotFound()
    order = await _lock_order_or_404(db, order_id, caller)
    if order.status != "delivered":
        raise OrderInvalidTransition(
            f"Cannot complete order in state {order.status!r}."
        )

    order.status = "completed"
    order.completed_at = _now()
    await db.flush()
    await _write_snapshot(db, order)
    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


async def _write_snapshot(db: AsyncSession, order: Order) -> None:
    """Insert analytics snapshot row (idempotent via ON CONFLICT)."""
    # Resolve store.city from the store row so snapshot is self-contained.
    store_result = await db.execute(
        sa.select(Store).where(Store.id == order.store_id)
    )
    store = store_result.scalar_one_or_none()
    if store is None:
        # Fallback: read the seller's city.
        seller_result = await db.execute(
            sa.select(Seller.city).where(Seller.id == order.seller_id)
        )
        city = seller_result.scalar_one_or_none() or ""
    else:
        # store.city is not a real column (Phase 4 uses sellers.city).
        seller_result = await db.execute(
            sa.select(Seller.city).where(Seller.id == order.seller_id)
        )
        city = seller_result.scalar_one_or_none() or ""

    # Count items
    count_result = await db.execute(
        sa.select(sa.func.coalesce(sa.func.sum(OrderItem.quantity), 0)).where(
            OrderItem.order_id == order.id
        )
    )
    item_count = int(count_result.scalar_one() or 0)

    stmt = pg_insert(OrderAnalyticsSnapshot).values(
        id=uuid.uuid4(),
        order_id=order.id,
        seller_id=order.seller_id,
        store_id=order.store_id,
        customer_id=order.customer_id,
        city=city,
        item_count=item_count,
        subtotal_minor=order.subtotal_minor,
        total_minor=order.total_minor,
        delivered_at=order.delivered_at or order.completed_at or _now(),
    ).on_conflict_do_nothing(index_elements=["order_id"])
    await db.execute(stmt)


async def cancel_order(
    db: AsyncSession,
    *,
    caller: User,
    order_id: uuid.UUID,
    reason: Optional[str],
) -> Order:
    """Cancel an order per the rules in the task spec / ADR-0012.

    - Customer: only in `pending`.
    - Seller: `pending`, `accepted`, `preparing`.
    - Admin: any pre-delivery state AND (post-out_for_delivery) only admin.
    """
    order = await _lock_order_or_404(db, order_id, caller)

    if order.status in TERMINAL_STATUSES or order.status == "delivered":
        raise OrderInvalidTransition(
            f"Cannot cancel order in state {order.status!r}."
        )

    role = caller.role
    if role == "customer":
        if order.status != "pending":
            raise OrderInvalidTransition(
                "Customers may only cancel orders in 'pending' state."
            )
    elif role == "seller":
        if order.status not in ("pending", "accepted", "preparing"):
            raise OrderInvalidTransition(
                "Seller may not cancel after out_for_delivery."
            )
    elif role == "admin":
        # Admin allowed in any pre-delivered state (including out_for_delivery).
        pass
    else:
        raise OrderNotFound()

    order.status = "cancelled"
    order.cancelled_at = _now()
    order.cancellation_reason = reason

    # Best-effort: cancel any outstanding driver request/assignment
    assignments = await db.execute(
        sa.select(DriverAssignment)
        .where(
            DriverAssignment.order_id == order.id,
            DriverAssignment.status.in_(("requested", "assigned", "accepted")),
        )
        .with_for_update()
    )
    for a in assignments.scalars().all():
        a.status = "cancelled"

    await db.flush()
    loaded = await _load_order_full(db, order.id)
    assert loaded is not None
    return loaded


# ---------------------------------------------------------------------------
# Listing / get
# ---------------------------------------------------------------------------


async def list_orders_for_caller(
    db: AsyncSession,
    caller: User,
    *,
    status: Optional[str] = None,
    limit: int = 50,
) -> list[Order]:
    stmt = (
        sa.select(Order)
        .options(
            selectinload(Order.order_items),
            selectinload(Order.delivery),
            selectinload(Order.driver_assignments),
        )
        .where(Order.deleted_at.is_(None))
        .order_by(Order.placed_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    if status is not None:
        stmt = stmt.where(Order.status == status)

    if caller.role == "admin":
        pass
    elif caller.role == "seller":
        stmt = stmt.where(Order.seller_id == caller.id)
    elif caller.role == "customer":
        stmt = stmt.where(Order.customer_id == caller.id)
    elif caller.role == "driver":
        # Driver sees orders where they are the assigned driver on delivery
        # OR the driver_id on driver_assignment (status assigned/accepted).
        sub_del = sa.select(Delivery.order_id).where(Delivery.driver_id == caller.id)
        sub_assign = sa.select(DriverAssignment.order_id).where(
            DriverAssignment.driver_id == caller.id,
            DriverAssignment.status.in_(("assigned", "accepted")),
        )
        stmt = stmt.where(
            sa.or_(Order.id.in_(sub_del), Order.id.in_(sub_assign))
        )
    else:
        return []

    result = await db.execute(stmt)
    return list(result.scalars().unique().all())


async def get_order_for_caller(
    db: AsyncSession,
    caller: User,
    order_id: uuid.UUID,
) -> Order:
    order = await _load_order_full(db, order_id)
    if order is None or order.deleted_at is not None:
        raise OrderNotFound()
    _ensure_can_view(order, caller)
    return order


# ---------------------------------------------------------------------------
# Delete (retention gated)
# ---------------------------------------------------------------------------


async def _get_retention_settings(db: AsyncSession) -> PlatformSettings:
    result = await db.execute(
        sa.select(PlatformSettings).where(PlatformSettings.id == 1)
    )
    ps = result.scalar_one_or_none()
    if ps is None:
        # Should never happen: seeded in migration 0001.
        ps = PlatformSettings(
            id=1, retention_min_days=30, order_auto_complete_grace_hours=72
        )
        db.add(ps)
        await db.flush()
    return ps


async def delete_order(
    db: AsyncSession,
    *,
    caller: User,
    order_id: uuid.UUID,
) -> None:
    """Hard-delete an order if retention window elapsed.

    Auth: customer who placed, seller who sold, or admin.  No admin override
    on retention (ADR-0012 D6).
    """
    order = await _load_order_locked(db, order_id)
    if order is None or order.deleted_at is not None:
        raise OrderNotFound()

    # Role-based access
    if caller.role == "customer" and order.customer_id != caller.id:
        raise OrderNotFound()
    if caller.role == "seller" and order.seller_id != caller.id:
        raise OrderNotFound()
    if caller.role == "driver":
        raise OrderNotFound()
    if caller.role not in ("customer", "seller", "admin"):
        raise OrderNotFound()

    terminal_at = _terminal_at(order)
    if terminal_at is None:
        raise OrderRetentionNotMet(
            "Order is not yet in a terminal state; retention has not started."
        )

    ps = await _get_retention_settings(db)
    if terminal_at.tzinfo is None:
        terminal_at = terminal_at.replace(tzinfo=timezone.utc)
    if _now() - terminal_at < timedelta(days=ps.retention_min_days):
        raise OrderRetentionNotMet()

    # Snapshot pre-flight in case the completion path skipped it (e.g. cancelled
    # orders never snapshot; that's fine — we only snapshot completed orders).
    if order.status == "completed":
        await _write_snapshot(db, order)
        await db.flush()

    # Hard-delete: rows on order_items, deliveries, driver_assignments cascade.
    await db.execute(sa.delete(Order).where(Order.id == order.id))
    await db.flush()


# ---------------------------------------------------------------------------
# Purge + auto-complete job
# ---------------------------------------------------------------------------


async def run_purge_job(
    db: AsyncSession,
) -> dict[str, int]:
    """Admin-triggerable purge + auto-complete job.

    1. Auto-complete delivered orders older than
       ``order_auto_complete_grace_hours``.  Writes snapshot atomically.
    2. Hard-delete terminal orders older than ``retention_min_days``.
    """
    ps = await _get_retention_settings(db)
    now = _now()

    auto_completed = 0
    grace_cutoff = now - timedelta(hours=ps.order_auto_complete_grace_hours)

    # 1) Auto-complete
    ac_result = await db.execute(
        sa.select(Order)
        .where(
            Order.status == "delivered",
            Order.delivered_at.is_not(None),
            Order.delivered_at <= grace_cutoff,
            Order.deleted_at.is_(None),
        )
        .with_for_update(skip_locked=True)
    )
    for order in ac_result.scalars().all():
        if order.status != "delivered":
            continue
        order.status = "completed"
        order.completed_at = now
        await db.flush()
        await _write_snapshot(db, order)
        await db.flush()
        auto_completed += 1

    # 2) Purge
    purged = 0
    retention_cutoff = now - timedelta(days=ps.retention_min_days)

    purge_candidates = await db.execute(
        sa.select(Order)
        .where(
            Order.status.in_(("completed", "cancelled")),
            Order.deleted_at.is_(None),
            sa.or_(
                sa.and_(Order.status == "completed", Order.completed_at <= retention_cutoff),
                sa.and_(Order.status == "cancelled", Order.cancelled_at <= retention_cutoff),
            ),
        )
        .with_for_update(skip_locked=True)
    )
    for order in purge_candidates.scalars().all():
        if order.status == "completed":
            await _write_snapshot(db, order)
            await db.flush()
        await db.execute(sa.delete(Order).where(Order.id == order.id))
        purged += 1

    await db.flush()
    return {"purged_count": purged, "auto_completed_count": auto_completed}


# ---------------------------------------------------------------------------
# Settings getters / setters
# ---------------------------------------------------------------------------


async def get_retention_settings(db: AsyncSession) -> PlatformSettings:
    return await _get_retention_settings(db)


async def update_retention_settings(
    db: AsyncSession,
    *,
    caller: User,
    retention_min_days: Optional[int] = None,
    order_auto_complete_grace_hours: Optional[int] = None,
) -> PlatformSettings:
    ps = await _get_retention_settings(db)
    if retention_min_days is not None:
        if retention_min_days < 1:
            from app.core.exceptions import RetentionSettingInvalid

            raise RetentionSettingInvalid()
        ps.retention_min_days = retention_min_days
    if order_auto_complete_grace_hours is not None:
        if order_auto_complete_grace_hours < 1:
            from app.core.exceptions import RetentionSettingInvalid

            raise RetentionSettingInvalid(
                "order_auto_complete_grace_hours must be >= 1."
            )
        ps.order_auto_complete_grace_hours = order_auto_complete_grace_hours
    ps.updated_at = _now()
    ps.updated_by_user_id = caller.id
    await db.flush()
    return ps


# ---------------------------------------------------------------------------
# Response helpers
# ---------------------------------------------------------------------------


def order_to_response_dict(order: Order) -> dict[str, Any]:
    delivery_dict: Optional[dict[str, Any]] = None
    if order.delivery is not None:
        d = order.delivery
        delivery_dict = {
            "id": d.id,
            "driver_id": d.driver_id,
            "seller_id": d.seller_id,
            "status": d.status,
            "started_at": d.started_at,
            "delivered_at": d.delivered_at,
        }

    active_assignment: Optional[dict[str, Any]] = None
    if order.driver_assignments:
        # Pick most recent non-cancelled assignment.
        candidates = [
            a for a in order.driver_assignments if a.status != "cancelled"
        ]
        if candidates:
            a = max(candidates, key=lambda x: x.requested_at)
            active_assignment = {
                "id": a.id,
                "driver_id": a.driver_id,
                "status": a.status,
                "requested_at": a.requested_at,
                "assigned_at": a.assigned_at,
            }

    return {
        "id": order.id,
        "customer_id": order.customer_id,
        "seller_id": order.seller_id,
        "store_id": order.store_id,
        "status": order.status,
        "subtotal_minor": order.subtotal_minor,
        "total_minor": order.total_minor,
        "delivery_address": order.delivery_address,
        "placed_at": order.placed_at,
        "accepted_at": order.accepted_at,
        "preparing_at": order.preparing_at,
        "out_for_delivery_at": order.out_for_delivery_at,
        "delivered_at": order.delivered_at,
        "completed_at": order.completed_at,
        "cancelled_at": order.cancelled_at,
        "cancellation_reason": order.cancellation_reason,
        "items": [
            {
                "id": i.id,
                "product_id": i.product_id,
                "product_name_snapshot": i.product_name_snapshot,
                "unit_price_minor_snapshot": i.unit_price_minor_snapshot,
                "quantity": i.quantity,
            }
            for i in order.order_items
        ],
        "delivery": delivery_dict,
        "driver_assignment": active_assignment,
    }
