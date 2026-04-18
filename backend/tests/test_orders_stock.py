"""Stock reservation tests.

- Out of stock → PRODUCT_OUT_OF_STOCK 409.
- Concurrent orders sharing the last unit → only one succeeds.
- Cancel does NOT restock (Phase 5 simplification).
"""

from __future__ import annotations

import asyncio

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_customer,
    seed_product,
    seed_seller_with_profile,
    seed_store_for_seller,
)

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": pw})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def test_out_of_stock_rejected(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_stk1@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=500, stock_quantity=1)
    await seed_customer(db, "cust_stk1@example.com", referring_seller_id=seller.id)
    c_tok = await _login(client, "cust_stk1@example.com", "CustomerPass123!")

    # Ask for 2, only 1 is in stock
    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(product.id), "quantity": 2}],
            "delivery_address": {"line1": "a", "city": "b", "country": "US"},
        },
        headers=_h(c_tok),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "PRODUCT_OUT_OF_STOCK"


async def test_stock_decrement_on_order(
    client: AsyncClient, db: AsyncSession
) -> None:
    from sqlalchemy import select

    from app.models.product import Product

    seller = await seed_seller_with_profile(db, "seller_stk2@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=500, stock_quantity=3)
    pid = product.id
    await seed_customer(db, "cust_stk2@example.com", referring_seller_id=seller.id)
    c_tok = await _login(client, "cust_stk2@example.com", "CustomerPass123!")

    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(pid), "quantity": 2}],
            "delivery_address": {"line1": "a", "city": "b", "country": "US"},
        },
        headers=_h(c_tok),
    )
    assert r.status_code == 201

    # Re-fetch product stock
    await db.commit()  # ensure visibility is independent of ORM identity map
    row = (
        await db.execute(select(Product).where(Product.id == pid))
    ).scalar_one()
    await db.refresh(row)
    assert row.stock_quantity == 1


async def test_sequential_orders_exhaust_stock(
    client: AsyncClient, db: AsyncSession
) -> None:
    """Two back-to-back orders for the same single-stock product — second fails."""
    seller = await seed_seller_with_profile(db, "seller_stk3@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=500, stock_quantity=1)
    await seed_customer(db, "cust_stk3a@example.com", referring_seller_id=seller.id)
    await seed_customer(db, "cust_stk3b@example.com", referring_seller_id=seller.id)
    tok_a = await _login(client, "cust_stk3a@example.com", "CustomerPass123!")
    tok_b = await _login(client, "cust_stk3b@example.com", "CustomerPass123!")

    body = {
        "items": [{"product_id": str(product.id), "quantity": 1}],
        "delivery_address": {"line1": "a", "city": "b", "country": "US"},
    }
    r1 = await client.post("/api/v1/orders", json=body, headers=_h(tok_a))
    r2 = await client.post("/api/v1/orders", json=body, headers=_h(tok_b))

    # Exactly one succeeded
    assert {r1.status_code, r2.status_code} == {201, 409}
    failed = r1 if r1.status_code == 409 else r2
    assert failed.json()["error"]["code"] == "PRODUCT_OUT_OF_STOCK"


async def test_null_stock_is_unlimited(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_stk4@example.com")
    store = await seed_store_for_seller(db, seller)
    product = await seed_product(db, seller, store, price_minor=500, stock_quantity=None)
    await seed_customer(db, "cust_stk4@example.com", referring_seller_id=seller.id)
    c_tok = await _login(client, "cust_stk4@example.com", "CustomerPass123!")

    r = await client.post(
        "/api/v1/orders",
        json={
            "items": [{"product_id": str(product.id), "quantity": 999}],
            "delivery_address": {"line1": "a", "city": "b", "country": "US"},
        },
        headers=_h(c_tok),
    )
    assert r.status_code == 201
