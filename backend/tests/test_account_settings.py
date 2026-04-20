"""Tests for account settings endpoints.

Covers:
- PATCH /api/v1/auth/me (update display_name, phone, avatar_url)
- POST /api/v1/auth/me/password (change password, wrong current password)
- GET /api/v1/auth/me/notifications (get prefs, auto-create defaults)
- PATCH /api/v1/auth/me/notifications (update subset of prefs)
- 401 without auth for all new endpoints

Run with: pytest -x -q tests/test_account_settings.py
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.conftest import seed_admin, seed_customer

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _get_access_token(client: AsyncClient, db: AsyncSession, email: str) -> str:
    """Create a customer user and return an access token."""
    await seed_customer(db, email)
    resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "CustomerPass123!"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# PATCH /auth/me — update profile
# ---------------------------------------------------------------------------


async def test_patch_me_update_display_name(client: AsyncClient, db: AsyncSession) -> None:
    """PATCH /me with display_name updates the field and returns the new value."""
    token = await _get_access_token(client, db, "patch_me_dn@example.com")

    resp = await client.patch(
        "/api/v1/auth/me",
        json={"display_name": "Updated Name"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Updated Name"

    # Verify GET /me reflects the change
    me_resp = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me_resp.status_code == 200
    assert me_resp.json()["display_name"] == "Updated Name"


async def test_patch_me_update_phone(client: AsyncClient, db: AsyncSession) -> None:
    """PATCH /me with phone updates only phone, leaves other fields intact."""
    token = await _get_access_token(client, db, "patch_me_phone@example.com")

    resp = await client.patch(
        "/api/v1/auth/me",
        json={"phone": "+15551234567"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["phone"] == "+15551234567"
    # display_name should be unchanged
    assert body["display_name"] == "Test Customer"


async def test_patch_me_update_avatar_url(client: AsyncClient, db: AsyncSession) -> None:
    """PATCH /me with avatar_url stores and returns the URL."""
    token = await _get_access_token(client, db, "patch_me_avatar@example.com")

    avatar = "https://cdn.example.com/avatars/user123.jpg"
    resp = await client.patch(
        "/api/v1/auth/me",
        json={"avatar_url": avatar},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["avatar_url"] == avatar


async def test_patch_me_partial_update_only_changes_provided_fields(
    client: AsyncClient, db: AsyncSession
) -> None:
    """PATCH /me with only one field does not touch others."""
    token = await _get_access_token(client, db, "patch_me_partial@example.com")

    # First set phone
    await client.patch(
        "/api/v1/auth/me",
        json={"phone": "+15550001111"},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Now update only display_name
    resp = await client.patch(
        "/api/v1/auth/me",
        json={"display_name": "Partial Update"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Partial Update"
    assert body["phone"] == "+15550001111"  # unchanged


async def test_patch_me_empty_body_returns_unchanged(
    client: AsyncClient, db: AsyncSession
) -> None:
    """PATCH /me with empty body returns current data unchanged."""
    token = await _get_access_token(client, db, "patch_me_empty@example.com")

    resp = await client.patch(
        "/api/v1/auth/me",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["display_name"] == "Test Customer"


async def test_patch_me_no_auth_returns_401(client: AsyncClient) -> None:
    """PATCH /me without auth token → 401."""
    resp = await client.patch(
        "/api/v1/auth/me",
        json={"display_name": "Hacker"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/me/password — change password
# ---------------------------------------------------------------------------


async def test_change_password_success(client: AsyncClient, db: AsyncSession) -> None:
    """POST /me/password with correct current password → 204, can login with new password."""
    email = "change_pw_ok@example.com"
    token = await _get_access_token(client, db, email)

    resp = await client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "CustomerPass123!", "new_password": "NewSecurePass99!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204

    # Verify login works with new password
    login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "NewSecurePass99!"},
    )
    assert login_resp.status_code == 200

    # Verify old password no longer works
    old_login_resp = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "CustomerPass123!"},
    )
    assert old_login_resp.status_code == 401


async def test_change_password_wrong_current_password(
    client: AsyncClient, db: AsyncSession
) -> None:
    """POST /me/password with wrong current password → 400 with correct detail."""
    token = await _get_access_token(client, db, "change_pw_bad@example.com")

    resp = await client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "WrongPassword999!", "new_password": "NewSecurePass99!"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 400
    body = resp.json()
    assert body["detail"] == "Current password is incorrect"


async def test_change_password_too_short(client: AsyncClient, db: AsyncSession) -> None:
    """POST /me/password with new_password < 8 chars → 422 validation error."""
    token = await _get_access_token(client, db, "change_pw_short@example.com")

    resp = await client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "CustomerPass123!", "new_password": "short"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


async def test_change_password_no_auth_returns_401(client: AsyncClient) -> None:
    """POST /me/password without auth → 401."""
    resp = await client.post(
        "/api/v1/auth/me/password",
        json={"current_password": "whatever", "new_password": "newpassword123"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /auth/me/notifications — get prefs
# ---------------------------------------------------------------------------


async def test_get_notifications_returns_defaults_when_no_prefs(
    client: AsyncClient, db: AsyncSession
) -> None:
    """GET /me/notifications auto-creates row with defaults for new user."""
    token = await _get_access_token(client, db, "notif_get_defaults@example.com")

    resp = await client.get(
        "/api/v1/auth/me/notifications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["push_enabled"] is True
    assert body["email_enabled"] is True
    assert body["order_updates"] is True
    assert body["messages"] is True
    assert body["marketing"] is False  # default off


async def test_get_notifications_no_auth_returns_401(client: AsyncClient) -> None:
    """GET /me/notifications without auth → 401."""
    resp = await client.get("/api/v1/auth/me/notifications")
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# PATCH /auth/me/notifications — update prefs
# ---------------------------------------------------------------------------


async def test_patch_notifications_updates_subset(
    client: AsyncClient, db: AsyncSession
) -> None:
    """PATCH /me/notifications with a subset of fields only changes those fields."""
    token = await _get_access_token(client, db, "notif_patch_subset@example.com")

    resp = await client.patch(
        "/api/v1/auth/me/notifications",
        json={"marketing": True, "push_enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["marketing"] is True
    assert body["push_enabled"] is False
    # Untouched defaults
    assert body["email_enabled"] is True
    assert body["order_updates"] is True
    assert body["messages"] is True


async def test_patch_notifications_persists_across_requests(
    client: AsyncClient, db: AsyncSession
) -> None:
    """PATCH then GET returns the updated values."""
    token = await _get_access_token(client, db, "notif_persist@example.com")

    # Turn off email notifications
    patch_resp = await client.patch(
        "/api/v1/auth/me/notifications",
        json={"email_enabled": False},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert patch_resp.status_code == 200

    # GET should reflect the change
    get_resp = await client.get(
        "/api/v1/auth/me/notifications",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["email_enabled"] is False


async def test_patch_notifications_empty_body_returns_unchanged(
    client: AsyncClient, db: AsyncSession
) -> None:
    """PATCH /me/notifications with empty body returns current prefs unchanged."""
    token = await _get_access_token(client, db, "notif_empty@example.com")

    # First set a value
    await client.patch(
        "/api/v1/auth/me/notifications",
        json={"marketing": True},
        headers={"Authorization": f"Bearer {token}"},
    )

    # Patch with empty body
    resp = await client.patch(
        "/api/v1/auth/me/notifications",
        json={},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["marketing"] is True  # unchanged


async def test_patch_notifications_no_auth_returns_401(client: AsyncClient) -> None:
    """PATCH /me/notifications without auth → 401."""
    resp = await client.patch(
        "/api/v1/auth/me/notifications",
        json={"marketing": True},
    )
    assert resp.status_code == 401
