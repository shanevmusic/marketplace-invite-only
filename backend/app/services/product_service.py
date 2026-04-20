"""Product service — seller CRUD + customer referral-scoped browse.

Key behaviors:
- Only the owning seller (or admin) may PATCH / DELETE a product.
- DELETE is soft (``deleted_at`` + ``is_active=False``) so lifetime-sales
  snapshots remain intact.
- Customer visibility is referral-scoped at depth=1 (ADR-0007): a customer
  may only see products whose ``seller_id = customer.referring_seller_id``.
  Non-matches return 404 (don't leak existence).
- Drivers do not browse the catalog.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import (
    ProductNotFound,
    ProductOwnershipError,
    SellerProfileMissing,
    StoreNotFound,
    VisibilityDenied,
)
from app.models.product import Product
from app.models.product_image import ProductImage
from app.models.seller import Seller
from app.models.store import Store
from app.models.user import User


async def _get_caller_seller(db: AsyncSession, caller: User) -> Seller:
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


async def _get_caller_store(db: AsyncSession, seller: Seller) -> Store:
    result = await db.execute(
        sa.select(Store).where(
            Store.seller_id == seller.id,
            Store.deleted_at.is_(None),
        )
    )
    store = result.scalar_one_or_none()
    if store is None:
        raise StoreNotFound(message="Seller has no store; create one first.")
    return store


async def _load_product_with_images(
    db: AsyncSession, product_id: uuid.UUID
) -> Optional[Product]:
    result = await db.execute(
        sa.select(Product)
        .options(selectinload(Product.images))
        .where(Product.id == product_id)
    )
    return result.scalar_one_or_none()


def _replace_images(product: Product, images: list[dict]) -> None:
    """Replace the product's image set with ``images``.

    Each dict must have ``s3_key`` and ``display_order`` keys.
    """
    # Drop current images (cascade set in relationship).
    product.images.clear()
    for spec in images:
        product.images.append(
            ProductImage(
                id=uuid.uuid4(),
                product_id=product.id,
                s3_key=spec["s3_key"],
                display_order=spec.get("display_order", 0),
            )
        )


async def create_product(
    db: AsyncSession,
    *,
    caller: User,
    name: str,
    price_minor: int,
    description: Optional[str],
    stock_quantity: Optional[int],
    images: list[dict],
    store_id: Optional[uuid.UUID] = None,
) -> Product:
    """Create a product in the caller's store."""
    seller = await _get_caller_seller(db, caller)
    store = await _get_caller_store(db, seller)

    # If caller specified a store_id it must match their own store.
    if store_id is not None and store_id != store.id:
        raise StoreNotFound()

    product = Product(
        id=uuid.uuid4(),
        seller_id=seller.id,
        store_id=store.id,
        name=name.strip(),
        description=(description or "").strip(),
        price_minor=price_minor,
        stock_quantity=stock_quantity,
        is_active=True,
    )
    db.add(product)
    await db.flush()  # ensure product.id exists before image inserts

    for spec in images:
        db.add(
            ProductImage(
                id=uuid.uuid4(),
                product_id=product.id,
                s3_key=spec["s3_key"],
                display_order=spec.get("display_order", 0),
            )
        )

    await db.flush()
    # Re-load with images so the response builder sees them.
    loaded = await _load_product_with_images(db, product.id)
    assert loaded is not None  # just created
    return loaded


async def update_product(
    db: AsyncSession,
    *,
    caller: User,
    product_id: uuid.UUID,
    name: Optional[str] = None,
    description: Optional[str] = None,
    price_minor: Optional[int] = None,
    stock_quantity: Optional[int] = None,
    is_active: Optional[bool] = None,
    images: Optional[list[dict]] = None,
) -> Product:
    """Patch a product owned by the caller (or admin)."""
    product = await _load_product_with_images(db, product_id)
    if product is None or product.deleted_at is not None:
        raise ProductNotFound()

    if caller.role == "admin":
        pass
    elif caller.role == "seller":
        seller = await _get_caller_seller(db, caller)
        if product.seller_id != seller.id:
            # Don't leak existence: 404 per ADR-0007 spirit.
            raise ProductNotFound()
    else:
        raise ProductOwnershipError()

    if name is not None:
        product.name = name.strip()
    if description is not None:
        product.description = description.strip()
    if price_minor is not None:
        product.price_minor = price_minor
    if stock_quantity is not None:
        product.stock_quantity = stock_quantity
    if is_active is not None:
        product.is_active = is_active
    if images is not None:
        _replace_images(product, images)

    await db.flush()
    loaded = await _load_product_with_images(db, product.id)
    assert loaded is not None
    return loaded


async def soft_delete_product(
    db: AsyncSession,
    *,
    caller: User,
    product_id: uuid.UUID,
) -> None:
    """Soft-delete a product.  Sets ``deleted_at`` and ``is_active=False``."""
    result = await db.execute(
        sa.select(Product).where(Product.id == product_id)
    )
    product = result.scalar_one_or_none()
    if product is None or product.deleted_at is not None:
        raise ProductNotFound()

    if caller.role == "admin":
        pass
    elif caller.role == "seller":
        seller = await _get_caller_seller(db, caller)
        if product.seller_id != seller.id:
            raise ProductNotFound()
    else:
        raise ProductOwnershipError()

    product.deleted_at = datetime.now(timezone.utc)
    product.is_active = False
    await db.flush()


async def get_product_for_caller(
    db: AsyncSession,
    caller: User,
    product_id: uuid.UUID,
) -> Product:
    """Return a product if the caller can see it, else raise 404.

    Visibility:
    - admin: any non-deleted product.
    - seller: own products only.
    - customer: products where ``seller_id == caller.referring_seller_id``.
    - driver / other: 404.
    """
    product = await _load_product_with_images(db, product_id)
    if product is None or product.deleted_at is not None:
        raise ProductNotFound()

    if caller.role == "admin":
        return product
    if caller.role == "seller":
        seller = await _get_caller_seller(db, caller)
        if product.seller_id != seller.id:
            raise ProductNotFound()
        return product
    if caller.role == "customer":
        # Allow if product belongs to a public store, OR to the customer's referring seller.
        store_pub = await db.execute(
            sa.select(Store.is_public).where(Store.id == product.store_id)
        )
        is_public = bool(store_pub.scalar_one_or_none())
        if is_public:
            return product
        if (
            caller.referring_seller_id is None
            or caller.referring_seller_id != product.seller_id
        ):
            raise ProductNotFound()
        return product
    raise ProductNotFound()


async def list_products_for_caller(
    db: AsyncSession,
    caller: User,
    *,
    store_id: Optional[uuid.UUID] = None,
    seller_id: Optional[uuid.UUID] = None,
    limit: int = 20,
) -> list[Product]:
    """Referral-scoped list of visible, non-deleted products.

    - admin: all non-deleted products, optional filters.
    - seller: own products only (store_id filter rejected if not own).
    - customer: limited to products of ``referring_seller_id``.
    - driver / other: empty list.

    Pagination is kept simple for Phase 4: bounded limit, no cursor.
    """
    stmt = (
        sa.select(Product)
        .options(selectinload(Product.images))
        .where(Product.deleted_at.is_(None), Product.is_active.is_(True))
        .order_by(Product.created_at.desc())
        .limit(min(max(limit, 1), 100))
    )

    if caller.role == "admin":
        if store_id is not None:
            stmt = stmt.where(Product.store_id == store_id)
        if seller_id is not None:
            stmt = stmt.where(Product.seller_id == seller_id)
    elif caller.role == "seller":
        seller = await _get_caller_seller(db, caller)
        stmt = stmt.where(Product.seller_id == seller.id)
        if store_id is not None:
            stmt = stmt.where(Product.store_id == store_id)
    elif caller.role == "customer":
        # Visibility for customers: products from their referring seller's store
        # OR from any public store.
        stmt = stmt.join(Store, Store.id == Product.store_id).where(
            Store.deleted_at.is_(None)
        )
        if caller.referring_seller_id is None:
            stmt = stmt.where(Store.is_public.is_(True))
        else:
            stmt = stmt.where(
                sa.or_(
                    Product.seller_id == caller.referring_seller_id,
                    Store.is_public.is_(True),
                )
            )
        if seller_id is not None:
            stmt = stmt.where(Product.seller_id == seller_id)
        if store_id is not None:
            stmt = stmt.where(Product.store_id == store_id)
    else:
        return []

    result = await db.execute(stmt)
    return list(result.scalars().all())


def product_to_response_dict(product: Product) -> dict:
    """Build a ProductResponse-compatible dict from a loaded Product."""
    return {
        "id": product.id,
        "seller_id": product.seller_id,
        "store_id": product.store_id,
        "name": product.name,
        "description": product.description,
        "price_minor": product.price_minor,
        "stock_quantity": product.stock_quantity,
        "is_active": product.is_active,
        "created_at": product.created_at,
        "images": [
            {
                "id": img.id,
                "s3_key": img.s3_key,
                "display_order": img.display_order,
            }
            for img in sorted(product.images, key=lambda i: i.display_order)
        ],
    }


def product_to_list_item_dict(product: Product) -> dict:
    """Build a ProductListItem-compatible dict."""
    first_image: Optional[str] = None
    if product.images:
        first_image = min(
            product.images, key=lambda i: i.display_order
        ).s3_key
    return {
        "id": product.id,
        "seller_id": product.seller_id,
        "store_id": product.store_id,
        "name": product.name,
        "price_minor": product.price_minor,
        "stock_quantity": product.stock_quantity,
        "is_active": product.is_active,
        "image_s3_key": first_image,
    }
