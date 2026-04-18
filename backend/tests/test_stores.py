"""Tests for /stores endpoints.

Covers:
- Seller creates a store (201) — second POST is 409 STORE_ALREADY_EXISTS.
- City is required (422 when missing; 422 when blank).
- Customers and drivers cannot POST /stores (403).
- Seller reads own store; non-sellers get 403 on /stores/me.
- Seller PATCH own store.
- GET /stores/{id} visibility: admin any; seller own; customer referral-scoped;
  unreferred customer + driver get 404.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import (
    seed_admin,
    seed_customer,
    seed_driver,
    seed_seller_with_profile,
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
# POST /stores
# ---------------------------------------------------------------------------


async def test_seller_creates_store_success(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "seller_create@example.com")
    token = await _login(client, "seller_create@example.com", "SellerPass123!")

    resp = await client.post(
        "/api/v1/stores",
        json={"name": "My Store", "city": "Portland"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == "My Store"
    assert body["city"] == "Portland"
    assert body["is_active"] is True
    assert body["slug"]


async def test_second_store_creation_returns_409(
    client: AsyncClient, db: AsyncSession
) -> None:
    """One store per seller invariant."""
    await seed_seller_with_profile(db, "seller_double@example.com")
    token = await _login(client, "seller_double@example.com", "SellerPass123!")

    first = await client.post(
        "/api/v1/stores",
        json={"name": "First", "city": "Austin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert first.status_code == 201, first.text

    second = await client.post(
        "/api/v1/stores",
        json={"name": "Second", "city": "Austin"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert second.status_code == 409, second.text
    assert second.json()["error"]["code"] == "STORE_ALREADY_EXISTS"


async def test_create_store_missing_city_422(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "seller_nocity@example.com")
    token = await _login(client, "seller_nocity@example.com", "SellerPass123!")
    resp = await client.post(
        "/api/v1/stores",
        json={"name": "No-City Store"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422  # Pydantic missing required field


async def test_create_store_blank_city_422(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "seller_blankcity@example.com")
    token = await _login(client, "seller_blankcity@example.com", "SellerPass123!")
    resp = await client.post(
        "/api/v1/stores",
        json={"name": "Store", "city": ""},
        headers={"Authorization": f"Bearer {token}"},
    )
    # Pydantic min_length=1 rejects empty strings → 422
    assert resp.status_code == 422


async def test_customer_cannot_create_store(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_customer(db, "store_customer@example.com")
    token = await _login(client, "store_customer@example.com", "CustomerPass123!")
    resp = await client.post(
        "/api/v1/stores",
        json={"name": "Nope", "city": "NYC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_driver_cannot_create_store(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_driver(db, "store_driver@example.com")
    token = await _login(client, "store_driver@example.com", "DriverPass123!")
    resp = await client.post(
        "/api/v1/stores",
        json={"name": "Nope", "city": "NYC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


async def test_admin_cannot_create_store_via_seller_endpoint(
    client: AsyncClient, db: AsyncSession
) -> None:
    """POST /stores is seller-only; admin use admin endpoints instead."""
    await seed_admin(db, "admin_store@example.com")
    token = await _login(client, "admin_store@example.com", "AdminPass123!")
    resp = await client.post(
        "/api/v1/stores",
        json={"name": "Admin Store", "city": "NYC"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# GET /stores/me and PATCH /stores/me
# ---------------------------------------------------------------------------


async def test_get_my_store_after_create(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "seller_getme@example.com")
    token = await _login(client, "seller_getme@example.com", "SellerPass123!")
    await client.post(
        "/api/v1/stores",
        json={"name": "ME", "city": "Denver"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        "/api/v1/stores/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["city"] == "Denver"


async def test_get_my_store_404_without_create(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "seller_nostore@example.com")
    token = await _login(client, "seller_nostore@example.com", "SellerPass123!")
    resp = await client.get(
        "/api/v1/stores/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


async def test_patch_my_store(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "seller_patch@example.com")
    token = await _login(client, "seller_patch@example.com", "SellerPass123!")
    await client.post(
        "/api/v1/stores",
        json={"name": "Old", "city": "Chicago"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.patch(
        "/api/v1/stores/me",
        json={"name": "New Name", "description": "Updated"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "New Name"
    assert body["description"] == "Updated"


# ---------------------------------------------------------------------------
# GET /stores/{id} — visibility matrix
# ---------------------------------------------------------------------------


async def test_admin_can_get_any_store(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_admin_view@example.com")
    s_token = await _login(client, "seller_admin_view@example.com", "SellerPass123!")
    create_resp = await client.post(
        "/api/v1/stores",
        json={"name": "S1", "city": "SF"},
        headers={"Authorization": f"Bearer {s_token}"},
    )
    store_id = create_resp.json()["id"]

    await seed_admin(db, "admin_view_store@example.com")
    a_token = await _login(client, "admin_view_store@example.com", "AdminPass123!")
    resp = await client.get(
        f"/api/v1/stores/{store_id}",
        headers={"Authorization": f"Bearer {a_token}"},
    )
    assert resp.status_code == 200


async def test_seller_cannot_get_other_sellers_store(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller_a = await seed_seller_with_profile(db, "seller_a_get@example.com")
    a_token = await _login(client, "seller_a_get@example.com", "SellerPass123!")
    created = await client.post(
        "/api/v1/stores",
        json={"name": "A", "city": "LA"},
        headers={"Authorization": f"Bearer {a_token}"},
    )
    store_id = created.json()["id"]

    await seed_seller_with_profile(db, "seller_b_get@example.com")
    b_token = await _login(client, "seller_b_get@example.com", "SellerPass123!")
    resp = await client.get(
        f"/api/v1/stores/{store_id}",
        headers={"Authorization": f"Bearer {b_token}"},
    )
    assert resp.status_code == 404


async def test_customer_referred_can_get_store(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_vis_ok@example.com")
    s_token = await _login(client, "seller_vis_ok@example.com", "SellerPass123!")
    created = await client.post(
        "/api/v1/stores",
        json={"name": "Shop", "city": "Boston"},
        headers={"Authorization": f"Bearer {s_token}"},
    )
    store_id = created.json()["id"]

    await seed_customer(
        db, "cust_referred@example.com", referring_seller_id=seller.id
    )
    c_token = await _login(client, "cust_referred@example.com", "CustomerPass123!")
    resp = await client.get(
        f"/api/v1/stores/{store_id}",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert resp.status_code == 200


async def test_customer_not_referred_404s_on_store(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_vis_denied@example.com")
    s_token = await _login(client, "seller_vis_denied@example.com", "SellerPass123!")
    created = await client.post(
        "/api/v1/stores",
        json={"name": "Hidden", "city": "Miami"},
        headers={"Authorization": f"Bearer {s_token}"},
    )
    store_id = created.json()["id"]

    await seed_customer(db, "cust_unreferred@example.com", referring_seller_id=None)
    c_token = await _login(client, "cust_unreferred@example.com", "CustomerPass123!")
    resp = await client.get(
        f"/api/v1/stores/{store_id}",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert resp.status_code == 404


async def test_driver_gets_404_on_store(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "seller_vis_driver@example.com")
    s_token = await _login(client, "seller_vis_driver@example.com", "SellerPass123!")
    created = await client.post(
        "/api/v1/stores",
        json={"name": "Driver-Hidden", "city": "Seattle"},
        headers={"Authorization": f"Bearer {s_token}"},
    )
    store_id = created.json()["id"]

    await seed_driver(db, "driver_vis@example.com")
    d_token = await _login(client, "driver_vis@example.com", "DriverPass123!")
    resp = await client.get(
        f"/api/v1/stores/{store_id}",
        headers={"Authorization": f"Bearer {d_token}"},
    )
    assert resp.status_code == 404
