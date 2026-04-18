"""WebSocket gateway tests (Phase 6).

Uses Starlette's sync TestClient which natively supports WebSocket
connections via ``client.websocket_connect``.  For the auth test we
pass a valid JWT via ``?token=<jwt>``.

These tests use psycopg2 (sync) to seed rows because TestClient runs
its own event loop portal; mixing asyncpg+asyncio.run would cross loops.
"""

from __future__ import annotations

import json
import uuid

import psycopg2
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.core.security import create_access_token, hash_password
from app.main import app


# NOTE: This file does NOT use pytestmark = pytest.mark.asyncio — TestClient is sync.


_DB_DSN = "postgresql://marketplace:marketplace@localhost:5432/marketplace_test"


def _mk_token(user_id: uuid.UUID, role: str) -> str:
    token, _ = create_access_token(user_id, role)
    return token


def _make_user_row(_unused, email: str, role: str) -> uuid.UUID:
    """Synchronously create a user in the test DB. Returns user id."""
    uid = uuid.uuid4()
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (id, email, password_hash, role, display_name, is_active) "
            "VALUES (%s, %s, %s, %s, %s, TRUE)",
            (str(uid), email, hash_password("WsTest1234!"), role, "WS"),
        )
        if role == "seller":
            cur.execute(
                "INSERT INTO sellers (id, user_id, display_name, bio, city, country_code) "
                "VALUES (%s, %s, %s, NULL, %s, %s)",
                (str(uid), str(uid), "WS", "Town", "US"),
            )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return uid


def _make_conversation(user_a: uuid.UUID, user_b: uuid.UUID) -> uuid.UUID:
    a, b = (user_a, user_b) if user_a.bytes < user_b.bytes else (user_b, user_a)
    cid = uuid.uuid4()
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO conversations (id, user_a_id, user_b_id) VALUES (%s, %s, %s)",
            (str(cid), str(a), str(b)),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()
    return cid


def _link_referral(customer_id: uuid.UUID, seller_id: uuid.UUID) -> None:
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET referring_seller_id=%s WHERE id=%s",
            (str(seller_id), str(customer_id)),
        )
        conn.commit()
        cur.close()
    finally:
        conn.close()


def _cleanup(ids: list[uuid.UUID], conv_ids: list[uuid.UUID]) -> None:
    conn = psycopg2.connect(_DB_DSN)
    try:
        cur = conn.cursor()
        for cid in conv_ids:
            cur.execute("DELETE FROM messages WHERE conversation_id=%s", (str(cid),))
            cur.execute("DELETE FROM conversations WHERE id=%s", (str(cid),))
        for uid in ids:
            cur.execute("DELETE FROM sellers WHERE id=%s", (str(uid),))
            cur.execute("DELETE FROM users WHERE id=%s", (str(uid),))
        conn.commit()
        cur.close()
    finally:
        conn.close()


@pytest.fixture(scope="module")
def tc(setup_test_db):
    with TestClient(app) as client:
        yield client


def test_ws_connect_without_token_closes_4401(tc: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with tc.websocket_connect("/ws") as ws:
            ws.receive_text()
    assert exc.value.code == 4401


def test_ws_connect_with_garbage_token_closes_4401(tc: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with tc.websocket_connect("/ws?token=garbage") as ws:
            ws.receive_text()
    assert exc.value.code == 4401


def test_ws_subscribe_non_participant_closes_4403(tc: TestClient) -> None:
    u_seller = _make_user_row(None, "ws_s1@example.com", "seller")
    u_cust = _make_user_row(None, "ws_c1@example.com", "customer")
    u_stranger = _make_user_row(None, "ws_c1_strange@example.com", "customer")

    cid = _make_conversation(u_seller, u_cust)
    try:
        tok = _mk_token(u_stranger, "customer")
        with pytest.raises(WebSocketDisconnect) as exc:
            with tc.websocket_connect(f"/ws?token={tok}") as ws:
                ws.send_text(
                    json.dumps({"type": "subscribe", "conversation_id": str(cid)})
                )
                # Wait for the server to close.
                ws.receive_text()
        assert exc.value.code == 4403
    finally:
        _cleanup([u_seller, u_cust, u_stranger], [cid])


def test_ws_subscribe_and_message_new_broadcast(tc: TestClient) -> None:
    from tests._crypto_helpers import b64url, new_keypair

    u_seller = _make_user_row(None, "ws_s2@example.com", "seller")
    u_cust = _make_user_row(None, "ws_c2@example.com", "customer")

    # Make cust referred by seller (needed for customer→seller eligibility,
    # but we will send from seller→customer: seller can always contact any
    # customer whose referring_seller_id == seller.id).
    _link_referral(u_cust, u_seller)

    cid = _make_conversation(u_seller, u_cust)
    try:
        cust_tok = _mk_token(u_cust, "customer")
        seller_tok = _mk_token(u_seller, "seller")

        with tc.websocket_connect(f"/ws?token={cust_tok}") as ws:
            ws.send_text(
                json.dumps({"type": "subscribe", "conversation_id": str(cid)})
            )
            ack = json.loads(ws.receive_text())
            assert ack["type"] == "subscribed"
            assert ack["conversation_id"] == str(cid)

            # Seller posts a message via REST from a separate sync client.
            _, eph_pub = new_keypair()
            payload = {
                "ciphertext_b64url": b64url(b"\x01" * 32),
                "nonce_b64url": b64url(b"\x02" * 12),
                "ephemeral_public_key_b64url": b64url(eph_pub),
            }
            r = tc.post(
                f"/api/v1/conversations/{cid}/messages",
                json=payload,
                headers={"Authorization": f"Bearer {seller_tok}"},
            )
            assert r.status_code == 201, r.text

            # Customer's subscribed socket should receive message.new.
            ws.settimeout = 2.0
            evt = json.loads(ws.receive_text())
            assert evt["type"] == "message.new"
            assert evt["conversation_id"] == str(cid)
            assert evt["message"]["sender_id"] == str(u_seller)
    finally:
        _cleanup([u_seller, u_cust], [cid])


def test_ws_ping_pong(tc: TestClient) -> None:
    u = _make_user_row(None, "ws_ping@example.com", "customer")
    try:
        tok = _mk_token(u, "customer")
        with tc.websocket_connect(f"/ws?token={tok}") as ws:
            ws.send_text(json.dumps({"type": "ping"}))
            evt = json.loads(ws.receive_text())
            assert evt["type"] == "pong"
    finally:
        _cleanup([u], [])


def test_ws_typing_event_sent_to_peer(tc: TestClient) -> None:
    u_seller = _make_user_row(None, "ws_t_s@example.com", "seller")
    u_cust = _make_user_row(None, "ws_t_c@example.com", "customer")
    cid = _make_conversation(u_seller, u_cust)
    try:
        seller_tok = _mk_token(u_seller, "seller")
        cust_tok = _mk_token(u_cust, "customer")
        with tc.websocket_connect(f"/ws?token={seller_tok}") as ws_s:
            ws_s.send_text(
                json.dumps({"type": "subscribe", "conversation_id": str(cid)})
            )
            json.loads(ws_s.receive_text())
            with tc.websocket_connect(f"/ws?token={cust_tok}") as ws_c:
                ws_c.send_text(
                    json.dumps(
                        {"type": "subscribe", "conversation_id": str(cid)}
                    )
                )
                json.loads(ws_c.receive_text())

                # Customer types — seller should receive a typing event.
                ws_c.send_text(
                    json.dumps(
                        {
                            "type": "typing",
                            "conversation_id": str(cid),
                            "state": "start",
                        }
                    )
                )
                evt = json.loads(ws_s.receive_text())
                assert evt["type"] == "typing"
                assert evt["state"] == "start"
                assert evt["from"] == str(u_cust)
    finally:
        _cleanup([u_seller, u_cust], [cid])
