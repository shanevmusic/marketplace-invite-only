"""Admin message-retention settings + purge tests (Phase 6)."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation import Conversation
from app.models.message import Message
from tests._crypto_helpers import b64url, new_keypair
from tests.conftest import (
    seed_admin,
    seed_customer,
    seed_seller_with_profile,
)

pytestmark = pytest.mark.asyncio


async def _login(client: AsyncClient, email: str, pw: str) -> str:
    r = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": pw}
    )
    assert r.status_code == 200
    return r.json()["access_token"]


def _h(t: str) -> dict:
    return {"Authorization": f"Bearer {t}"}


async def test_get_and_patch_message_retention(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, "admin_mr_1@example.com")
    at = await _login(client, "admin_mr_1@example.com", "AdminPass123!")

    r = await client.get(
        "/api/v1/admin/settings/message-retention", headers=_h(at)
    )
    assert r.status_code == 200
    assert r.json()["message_retention_days"] == 90

    r = await client.patch(
        "/api/v1/admin/settings/message-retention",
        json={"message_retention_days": 14},
        headers=_h(at),
    )
    assert r.status_code == 200
    assert r.json()["message_retention_days"] == 14


async def test_patch_rejects_below_minimum(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_admin(db, "admin_mr_2@example.com")
    at = await _login(client, "admin_mr_2@example.com", "AdminPass123!")
    r = await client.patch(
        "/api/v1/admin/settings/message-retention",
        json={"message_retention_days": 3},
        headers=_h(at),
    )
    assert r.status_code == 422


async def test_non_admin_forbidden(
    client: AsyncClient, db: AsyncSession
) -> None:
    await seed_seller_with_profile(db, "admin_mr_seller@example.com")
    tok = await _login(
        client, "admin_mr_seller@example.com", "SellerPass123!"
    )
    r = await client.patch(
        "/api/v1/admin/settings/message-retention",
        json={"message_retention_days": 14},
        headers=_h(tok),
    )
    assert r.status_code == 403
    r = await client.post(
        "/api/v1/admin/jobs/purge-messages", headers=_h(tok)
    )
    assert r.status_code == 403


async def test_purge_removes_old_messages_only(
    client: AsyncClient, db: AsyncSession
) -> None:
    seller = await seed_seller_with_profile(db, "admin_mr_s3@example.com")
    cust = await seed_customer(
        db, "admin_mr_c3@example.com", referring_seller_id=seller.id
    )
    admin = await seed_admin(db, "admin_mr_3@example.com")

    at = await _login(client, "admin_mr_3@example.com", "AdminPass123!")

    # Retention to 7 days.
    r = await client.patch(
        "/api/v1/admin/settings/message-retention",
        json={"message_retention_days": 7},
        headers=_h(at),
    )
    assert r.status_code == 200

    # Create a conversation + two messages directly (one old, one new).
    a, b = (
        (seller.id, cust.id)
        if seller.id.bytes < cust.id.bytes
        else (cust.id, seller.id)
    )
    conv = Conversation(
        id=uuid.uuid4(), user_a_id=a, user_b_id=b, created_at=datetime.now(timezone.utc)
    )
    db.add(conv)
    await db.flush()

    old_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        sender_id=seller.id,
        ciphertext=b"\x01" * 16,
        nonce=b"\x02" * 12,
        ephemeral_public_key=b"\x03" * 32,
        sent_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    new_msg = Message(
        id=uuid.uuid4(),
        conversation_id=conv.id,
        sender_id=seller.id,
        ciphertext=b"\x04" * 16,
        nonce=b"\x05" * 12,
        ephemeral_public_key=b"\x06" * 32,
        sent_at=datetime.now(timezone.utc),
    )
    db.add_all([old_msg, new_msg])
    await db.flush()

    r = await client.post(
        "/api/v1/admin/jobs/purge-messages", headers=_h(at)
    )
    assert r.status_code == 200
    assert r.json()["purged_count"] >= 1

    remaining = await db.execute(
        sa.select(Message).where(Message.conversation_id == conv.id)
    )
    ids = [m.id for m in remaining.scalars().all()]
    assert new_msg.id in ids
    assert old_msg.id not in ids
