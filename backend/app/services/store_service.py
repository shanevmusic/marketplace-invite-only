"""Store service — one store per seller, city-scoped.

Business rules (frozen per Phase 4 scope):
- One store per seller (409 STORE_ALREADY_EXISTS on duplicate).
- City is required and lives on ``sellers.city`` (ADR-0010).
- Customers may only read a store whose seller is their direct referring
  seller (depth=1, ADR-0007).  Non-matches return 404 — do NOT leak.
"""

from __future__ import annotations

import re
import uuid
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    SellerProfileMissing,
    StoreAlreadyExists,
    StoreCityRequired,
    StoreNotFound,
    VisibilityDenied,
)
from app.models.seller import Seller
from app.models.store import Store
from app.models.user import User


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slugify(value: str) -> str:
    """Return a lowercase URL-safe slug for ``value``."""
    slug = _SLUG_RE.sub("-", value.lower()).strip("-")
    return slug or "store"


async def _unique_slug(db: AsyncSession, base: str) -> str:
    """Generate a unique slug derived from ``base``."""
    candidate = base
    suffix = 0
    while True:
        exists = await db.execute(
            sa.select(Store.id).where(Store.slug == candidate)
        )
        if exists.scalar_one_or_none() is None:
            return candidate
        suffix += 1
        candidate = f"{base}-{suffix}"


async def _get_caller_seller(db: AsyncSession, user: User) -> Seller:
    """Return the caller's Seller row or raise 400 SELLER_PROFILE_MISSING."""
    result = await db.execute(
        sa.select(Seller).where(
            Seller.user_id == user.id,
            Seller.deleted_at.is_(None),
        )
    )
    seller = result.scalar_one_or_none()
    if seller is None:
        raise SellerProfileMissing()
    return seller


async def create_store(
    db: AsyncSession,
    *,
    caller: User,
    name: str,
    city: str,
    description: Optional[str] = None,
    slug: Optional[str] = None,
) -> Store:
    """Create the caller's one store.

    Raises:
        SellerProfileMissing — caller has no sellers row.
        StoreCityRequired — city is empty/whitespace.
        StoreAlreadyExists — caller already owns a store.
    """
    if not city or not city.strip():
        raise StoreCityRequired()
    if not name or not name.strip():
        raise StoreCityRequired(message="Store name is required.")

    seller = await _get_caller_seller(db, caller)

    # Enforce one store per seller at the service layer (DB also enforces via
    # uq_stores_seller_id).
    existing = await db.execute(
        sa.select(Store).where(
            Store.seller_id == seller.id,
            Store.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise StoreAlreadyExists()

    # Persist the city on the seller profile (single source of truth).
    seller.city = city.strip()

    final_slug = slug.strip().lower() if slug else _slugify(name)
    final_slug = await _unique_slug(db, final_slug)

    store = Store(
        id=uuid.uuid4(),
        seller_id=seller.id,
        name=name.strip(),
        slug=final_slug,
        description=(description or "").strip(),
    )
    db.add(store)
    try:
        await db.flush()
    except IntegrityError as exc:  # race: two concurrent POSTs
        await db.rollback()
        raise StoreAlreadyExists() from exc
    await db.refresh(store)
    return store


async def get_own_store(db: AsyncSession, caller: User) -> Store:
    """Return the caller seller's store or raise 404."""
    seller = await _get_caller_seller(db, caller)
    result = await db.execute(
        sa.select(Store).where(
            Store.seller_id == seller.id,
            Store.deleted_at.is_(None),
        )
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise StoreNotFound()
    return store


async def update_own_store(
    db: AsyncSession,
    *,
    caller: User,
    name: Optional[str] = None,
    city: Optional[str] = None,
    description: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Store:
    """Patch the caller's store (fields not provided are left unchanged)."""
    seller = await _get_caller_seller(db, caller)
    result = await db.execute(
        sa.select(Store).where(
            Store.seller_id == seller.id,
            Store.deleted_at.is_(None),
        )
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise StoreNotFound()

    if name is not None:
        if not name.strip():
            raise StoreCityRequired(message="Store name is required.")
        store.name = name.strip()
    if city is not None:
        if not city.strip():
            raise StoreCityRequired()
        seller.city = city.strip()
    if description is not None:
        store.description = description.strip()
    if is_active is not None:
        store.is_active = is_active

    await db.flush()
    await db.refresh(store)
    return store


async def _get_seller_by_store(
    db: AsyncSession, store: Store
) -> Seller:
    result = await db.execute(
        sa.select(Seller).where(Seller.id == store.seller_id)
    )
    seller = result.scalar_one()
    return seller


async def get_store_for_caller(
    db: AsyncSession,
    caller: User,
    store_id: uuid.UUID,
) -> tuple[Store, Seller]:
    """Return store + its seller, applying visibility rules for the caller.

    Visibility:
    - admin: any non-deleted store.
    - seller: only own store (404 otherwise — do not leak existence).
    - customer: only store belonging to their ``referring_seller_id`` (depth=1).
    - driver: 404 — drivers do not browse the catalog in Phase 4.
    Soft-deleted stores return 404 for non-admin callers.
    """
    result = await db.execute(
        sa.select(Store).where(Store.id == store_id)
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise StoreNotFound()
    if store.deleted_at is not None and caller.role != "admin":
        raise StoreNotFound()

    seller = await _get_seller_by_store(db, store)

    if caller.role == "admin":
        return store, seller
    if caller.role == "seller":
        if seller.user_id != caller.id:
            raise StoreNotFound()
        return store, seller
    if caller.role == "customer":
        if caller.referring_seller_id is None or caller.referring_seller_id != seller.id:
            raise VisibilityDenied()
        return store, seller
    # driver or any other role
    raise StoreNotFound()


def store_to_response_dict(store: Store, seller: Seller) -> dict:
    """Build a StoreResponse-compatible dict (city comes from the seller)."""
    return {
        "id": store.id,
        "seller_id": store.seller_id,
        "name": store.name,
        "slug": store.slug,
        "description": store.description,
        "city": seller.city,
        "is_active": store.is_active,
        "created_at": store.created_at,
    }
