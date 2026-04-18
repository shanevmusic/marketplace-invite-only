"""Tests for /products endpoints.

Covers:
- Seller CRUD on own products (create, patch, delete).
- Non-owner seller cannot patch/delete another seller's product (404).
- Admin can patch/delete any product.
- Image metadata persists on create and full-replace on patch.
- Customer / driver cannot POST /products (403).
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_admin,
    seed_customer,
    seed_driver,
    seed_product,
    seed_seller_with_profile,
    seed_store_for_seller,
)

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, password: str) -> str:
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# Seller CRUD on own products
# ---------------------------------------------------------------------------


async def test_seller_creates_product_with_images(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "prodseller1@example.com")
    await seed_store_for_seller(db, seller)
    token = await _login(client, "prodseller1@example.com", "SellerPass123!")

    resp = await client.post(
        "/api/v1/products",
        json={
            "name": "Widget",
            "price_minor": 1999,
            "stock_quantity": 5,
            "description": "A widget",
            "images": [
                {"s3_key": "s3://bucket/widget-1.jpg", "display_order": 0},
                {"s3_key": "s3://bucket/widget-2.jpg", "display_order": 1},
            ],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "Widget"
    assert body["price_minor"] == 1999
    assert len(body["images"]) == 2
    assert body["images"][0]["s3_key"].endswith("-1.jpg")


async def test_seller_patches_own_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "prodseller2@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, name="Old")
    token = await _login(client, "prodseller2@example.com", "SellerPass123!")

    resp = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"name": "New", "price_minor": 3000},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "New"
    assert body["price_minor"] == 3000


async def test_seller_soft_deletes_own_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "prodseller3@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store)
    token = await _login(client, "prodseller3@example.com", "SellerPass123!")

    resp = await client.delete(
        f"/api/v1/products/{product.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # After delete, GET returns 404 even for the owner (soft-deleted).
    get_resp = await client.get(
        f"/api/v1/products/{product.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 404


async def test_patch_replaces_images(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "prodseller4@example.com")
    await seed_store_for_seller(db, seller)
    token = await _login(client, "prodseller4@example.com", "SellerPass123!")

    create = await client.post(
        "/api/v1/products",
        json={
            "name": "P",
            "price_minor": 500,
            "images": [{"s3_key": "s3://old.jpg", "display_order": 0}],
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    pid = create.json()["id"]

    patch = await client.patch(
        f"/api/v1/products/{pid}",
        json={
            "images": [
                {"s3_key": "s3://new-a.jpg", "display_order": 0},
                {"s3_key": "s3://new-b.jpg", "display_order": 1},
            ]
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch.status_code == 200
    imgs = patch.json()["images"]
    assert len(imgs) == 2
    assert imgs[0]["s3_key"] == "s3://new-a.jpg"


# ---------------------------------------------------------------------------
# Ownership / RBAC
# ---------------------------------------------------------------------------


async def test_non_owner_seller_cannot_patch_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Seller B patching Seller A's product → 404 (don't leak existence)."""
    seller_a = await seed_seller_with_profile(db, "prod_a@example.com")
    store_a = await seed_store_for_seller(db, seller_a)
    product = await seed_product(db, seller_a, store_a)

    await seed_seller_with_profile(db, "prod_b@example.com")
    b_token = await _login(client, "prod_b@example.com", "SellerPass123!")

    resp = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"name": "Hijacked"},
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_non_owner_seller_cannot_delete_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller_a = await seed_seller_with_profile(db, "del_a@example.com")
    store_a = await seed_store_for_seller(db, seller_a)
    product = await seed_product(db, seller_a, store_a)

    await seed_seller_with_profile(db, "del_b@example.com")
    b_token = await _login(client, "del_b@example.com", "SellerPass123!")

    resp = await client.delete(
        f"/api/v1/products/{product.id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_admin_can_delete_any_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "admin_del_seller@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store)

    await seed_admin(db, "admin_del@example.com")
    a_token = await _login(client, "admin_del@example.com", "AdminPass123!")

    resp = await client.delete(
        f"/api/v1/products/{product.id}",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 204


async def test_admin_can_patch_any_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "admin_patch_s@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store)

    await seed_admin(db, "admin_patch@example.com")
    a_token = await _login(client, "admin_patch@example.com", "AdminPass123!")

    resp = await client.patch(
        f"/api/v1/products/{product.id}",
        json={"name": "Moderated"},
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Moderated"


async def test_customer_cannot_create_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_customer(db, "prod_cust@example.com")
    token = await _login(client, "prod_cust@example.com", "CustomerPass123!")

    resp = await client.post(
        "/api/v1/products",
        json={"name": "Nope", "price_minor": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_driver_cannot_create_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_driver(db, "prod_driver@example.com")
    token = await _login(client, "prod_driver@example.com", "DriverPass123!")

    resp = await client.post(
        "/api/v1/products",
        json={"name": "Nope", "price_minor": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_seller_without_store_cannot_create_product(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Seller who has not created a store → 404 STORE_NOT_FOUND."""
    await seed_seller_with_profile(db, "nostore_seller@example.com")
    token = await _login(client, "nostore_seller@example.com", "SellerPass123!")

    resp = await client.post(
        "/api/v1/products",
        json={"name": "Nope", "price_minor": 100},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_product_creation_requires_positive_price(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "price_seller@example.com")
    await seed_store_for_seller(db, seller)
    token = await _login(client, "price_seller@example.com", "SellerPass123!")

    resp = await client.post(
        "/api/v1/products",
        json={"name": "Free", "price_minor": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422  # pydantic gt=0
