"""WebSocket gateway — in-process fanout for conversation + delivery events.

This gateway is the minimal single-process pub/sub. A Redis pub/sub is
the Phase 12 upgrade for multi-node deployment.

Close codes:
- 4401 — missing/invalid/expired JWT at handshake or during session.
- 4403 — caller is not a participant of the conversation/order they tried to join.

Messaging events (Phase 6):
- ``message.new``
- ``message.read``
- ``typing``

Delivery tracking events (Phase 7):
- ``delivery.location`` — lat/lng breadcrumb. INTERNAL ONLY.
  Dispatched only to driver/seller/admin subscribers.
- ``delivery.eta``       — ETA update.  Customer-safe.  Dispatched to all.
- ``delivery.status``    — status transition.  Customer-safe.  Dispatched to all.

CRITICAL: the delivery subscriber registry partitions subscribers by role
into ``internal`` (driver/seller/admin) and ``customer``.  A customer-role
subscriber is NEVER in the internal bucket, so even a bug that tried to
broadcast a lat/lng to "everyone on the order" cannot reach a customer —
the dispatcher routes by payload TYPE, not by string filtering.

Client → server messages (JSON):
- ``{"type":"subscribe","conversation_id":"..."}``          — messaging
- ``{"type":"subscribe","delivery_order_id":"..."}``        — delivery
- ``{"type":"unsubscribe","conversation_id":"..."}``
- ``{"type":"unsubscribe","delivery_order_id":"..."}``
- ``{"type":"typing","conversation_id":"...","state":"start"|"stop"}``
- ``{"type":"ping"}``
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

import sqlalchemy as sa
from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect, WebSocketState
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AuthenticationError, InvalidTokenError, TokenExpired
from app.core.security import decode_access_token
from app.db.session import AsyncSessionFactory
from app.models.conversation import Conversation
from app.models.user import User


logger = logging.getLogger("marketplace.ws")


HEARTBEAT_INTERVAL_SECONDS = 30
CLOSE_AUTH = 4401
CLOSE_FORBIDDEN = 4403


DeliveryRole = Literal["internal", "customer"]


# ---------------------------------------------------------------------------
# Connection registry
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class WSConnection:
    """Identity-equal dataclass so instances are hashable for set membership."""

    ws: WebSocket
    user_id: uuid.UUID
    user_role: str
    conversations: set[uuid.UUID] = field(default_factory=set)
    delivery_orders: set[uuid.UUID] = field(default_factory=set)

    def __hash__(self) -> int:
        return id(self)


class ConnectionRegistry:
    """Thread-safe (single-event-loop) fanout registry."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # conversation_id -> set of connections subscribed (messaging)
        self._subs: dict[uuid.UUID, set[WSConnection]] = {}
        # order_id -> {"internal": set[conn], "customer": set[conn]}
        # Partitioning by ROLE not by event type: customers and internal
        # subscribers live in physically different buckets and the
        # dispatcher picks the right bucket per event type.
        self._delivery_subs: dict[
            uuid.UUID, dict[DeliveryRole, set[WSConnection]]
        ] = {}

    # Messaging ------------------------------------------------------------
    async def subscribe(self, conn: WSConnection, conversation_id: uuid.UUID) -> None:
        async with self._lock:
            conn.conversations.add(conversation_id)
            self._subs.setdefault(conversation_id, set()).add(conn)

    async def unsubscribe(
        self, conn: WSConnection, conversation_id: uuid.UUID
    ) -> None:
        async with self._lock:
            conn.conversations.discard(conversation_id)
            subs = self._subs.get(conversation_id)
            if subs is not None:
                subs.discard(conn)
                if not subs:
                    del self._subs[conversation_id]

    async def subscribers_of(
        self, conversation_id: uuid.UUID
    ) -> list[WSConnection]:
        async with self._lock:
            return list(self._subs.get(conversation_id, set()))

    # Delivery -------------------------------------------------------------
    async def subscribe_delivery(
        self,
        conn: WSConnection,
        order_id: uuid.UUID,
        role: DeliveryRole,
    ) -> None:
        async with self._lock:
            conn.delivery_orders.add(order_id)
            topic = self._delivery_subs.setdefault(
                order_id, {"internal": set(), "customer": set()}
            )
            topic[role].add(conn)

    async def unsubscribe_delivery(
        self, conn: WSConnection, order_id: uuid.UUID
    ) -> None:
        async with self._lock:
            conn.delivery_orders.discard(order_id)
            topic = self._delivery_subs.get(order_id)
            if topic is not None:
                topic["internal"].discard(conn)
                topic["customer"].discard(conn)
                if not topic["internal"] and not topic["customer"]:
                    del self._delivery_subs[order_id]

    async def delivery_internal_subscribers(
        self, order_id: uuid.UUID
    ) -> list[WSConnection]:
        async with self._lock:
            topic = self._delivery_subs.get(order_id)
            if topic is None:
                return []
            return list(topic["internal"])

    async def delivery_customer_subscribers(
        self, order_id: uuid.UUID
    ) -> list[WSConnection]:
        async with self._lock:
            topic = self._delivery_subs.get(order_id)
            if topic is None:
                return []
            return list(topic["customer"])

    # Disconnect -----------------------------------------------------------
    async def disconnect_all(self, conn: WSConnection) -> None:
        async with self._lock:
            for cid in list(conn.conversations):
                subs = self._subs.get(cid)
                if subs is not None:
                    subs.discard(conn)
                    if not subs:
                        del self._subs[cid]
            conn.conversations.clear()
            for oid in list(conn.delivery_orders):
                topic = self._delivery_subs.get(oid)
                if topic is not None:
                    topic["internal"].discard(conn)
                    topic["customer"].discard(conn)
                    if not topic["internal"] and not topic["customer"]:
                        del self._delivery_subs[oid]
            conn.delivery_orders.clear()


_registry = ConnectionRegistry()


# ---------------------------------------------------------------------------
# Broadcast helpers — imported by REST handlers.
# ---------------------------------------------------------------------------


def _json_default(obj: Any) -> Any:
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, bytes):
        import base64

        return base64.urlsafe_b64encode(obj).rstrip(b"=").decode("ascii")
    raise TypeError(f"Not JSON serializable: {type(obj).__name__}")


async def _send_text(conn: "WSConnection", text: str) -> None:
    try:
        await conn.ws.send_text(text)
    except Exception:  # noqa: BLE001
        logger.debug("drop broadcast to dead socket user=%s", conn.user_id)


async def _broadcast_event(
    conversation_id: uuid.UUID, event: dict[str, Any]
) -> None:
    subs = await _registry.subscribers_of(conversation_id)
    if not subs:
        return
    text = json.dumps(event, default=_json_default)
    for conn in subs:
        await _send_text(conn, text)


async def broadcast_message_new(
    conversation_id: uuid.UUID, payload: dict[str, Any]
) -> None:
    event = {
        "type": "message.new",
        "conversation_id": str(conversation_id),
        "message": payload,
    }
    await _broadcast_event(conversation_id, event)


async def broadcast_message_read(
    conversation_id: uuid.UUID, payload: dict[str, Any]
) -> None:
    event = {
        "type": "message.read",
        "conversation_id": str(conversation_id),
        "message": payload,
    }
    await _broadcast_event(conversation_id, event)


# ---------------------------------------------------------------------------
# Delivery tracking broadcasters (Phase 7)
# ---------------------------------------------------------------------------


async def broadcast_delivery_location_internal(
    order_id: uuid.UUID, event: dict[str, Any]
) -> None:
    """Send a ``delivery.location`` event to INTERNAL subscribers only.

    Because internal and customer subscribers live in different buckets,
    it is structurally impossible for this call to reach a customer
    socket — even if a dev accidentally calls it on every event type.
    """
    subs = await _registry.delivery_internal_subscribers(order_id)
    if not subs:
        return
    text = json.dumps(event, default=_json_default)
    for conn in subs:
        await _send_text(conn, text)


async def broadcast_delivery_event_all(
    order_id: uuid.UUID, event: dict[str, Any]
) -> None:
    """Send a customer-safe event (eta, status) to BOTH buckets.

    Caller guarantees the event contains no coordinate fields.  The
    dispatcher does not re-validate here (that is the schema's job at
    the call site) but the bucketing means that if this helper is ever
    misused for location data, it still reaches internal-plus-customer
    not only internal — which is the visible bug.  The inverse (customer
    leak) is prevented by the bucket separation because
    ``broadcast_delivery_location_internal`` has no customer path at all.
    """
    internal_subs = await _registry.delivery_internal_subscribers(order_id)
    customer_subs = await _registry.delivery_customer_subscribers(order_id)
    if not internal_subs and not customer_subs:
        return
    text = json.dumps(event, default=_json_default)
    for conn in internal_subs:
        await _send_text(conn, text)
    for conn in customer_subs:
        await _send_text(conn, text)


# ---------------------------------------------------------------------------
# Handshake auth
# ---------------------------------------------------------------------------


def _extract_token(ws: WebSocket) -> str | None:
    # 1) ?token=<jwt>
    token = ws.query_params.get("token")
    if token:
        return token
    # 2) Authorization: Bearer
    auth = ws.headers.get("authorization") or ws.headers.get("Authorization")
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    return None


async def _authenticate(ws: WebSocket) -> User | None:
    token = _extract_token(ws)
    if not token:
        return None
    try:
        payload = decode_access_token(token)
    except (AuthenticationError, InvalidTokenError, TokenExpired, Exception):  # noqa: BLE001
        return None
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            sa.select(User).where(
                User.id == uuid.UUID(payload.sub),
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if user is None or not user.is_active or user.disabled_at is not None:
            return None
        # Detach from the session (we don't need to track it past auth).
        session.expunge(user)
        return user


async def _is_participant(
    conversation_id: uuid.UUID, user_id: uuid.UUID, user_role: str
) -> bool:
    async with AsyncSessionFactory() as session:
        result = await session.execute(
            sa.select(Conversation).where(Conversation.id == conversation_id)
        )
        conv = result.scalar_one_or_none()
        if conv is None:
            return False
        if user_role == "admin":
            return True
        return user_id in (conv.user_a_id, conv.user_b_id)


async def _resolve_delivery_role(
    order_id: uuid.UUID, user: User
) -> DeliveryRole | None:
    """Return 'internal' / 'customer' / None.

    Uses a fresh session (like the other _authenticate helpers) — the WS
    handler does not share ``get_db`` with the REST endpoint.
    """
    from app.services.delivery_tracking_service import load_order, resolve_role

    async with AsyncSessionFactory() as session:
        order = await load_order(session, order_id)
        if order is None:
            return None
        role = await resolve_role(session, user=user, order=order)
    if role == "none":
        return None
    if role == "customer":
        return "customer"
    return "internal"


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------


async def handle_ws(ws: WebSocket) -> None:
    user = await _authenticate(ws)
    if user is None:
        # Must accept() first so Starlette sends our custom 4401 close
        # frame on the open socket (pre-accept close goes to HTTP 403/1008).
        await ws.accept()
        await ws.close(code=CLOSE_AUTH)
        return

    await ws.accept()
    conn = WSConnection(ws=ws, user_id=user.id, user_role=user.role)

    # Observability — count active WS connections.
    try:
        from app.core.observability import ws_connections_active
        ws_connections_active.inc()
    except Exception:  # noqa: BLE001
        pass

    # Heartbeat task
    heartbeat_task = asyncio.create_task(_heartbeat(conn))
    try:
        while True:
            try:
                raw = await ws.receive_text()
            except WebSocketDisconnect:
                return
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await _safe_send(
                    conn,
                    {"type": "error", "error": "invalid_json"},
                )
                continue

            mtype = msg.get("type")
            if mtype == "ping":
                await _safe_send(conn, {"type": "pong"})
                continue

            if mtype == "subscribe":
                # Delivery tracking subscribe?
                if msg.get("delivery_order_id") is not None:
                    oid_str = msg.get("delivery_order_id")
                    try:
                        oid = uuid.UUID(oid_str)
                    except (ValueError, TypeError):
                        await _safe_send(conn, {"type": "error", "error": "invalid_delivery_order_id"})
                        continue
                    role = await _resolve_delivery_role(oid, user)
                    if role is None:
                        await ws.close(code=CLOSE_FORBIDDEN)
                        return
                    await _registry.subscribe_delivery(conn, oid, role)
                    await _safe_send(
                        conn,
                        {"type": "delivery.subscribed", "order_id": str(oid)},
                    )
                    continue

                cid_str = msg.get("conversation_id")
                if not cid_str:
                    await _safe_send(conn, {"type": "error", "error": "missing_conversation_id"})
                    continue
                try:
                    cid = uuid.UUID(cid_str)
                except ValueError:
                    await _safe_send(conn, {"type": "error", "error": "invalid_conversation_id"})
                    continue
                if not await _is_participant(cid, user.id, user.role):
                    await ws.close(code=CLOSE_FORBIDDEN)
                    return
                await _registry.subscribe(conn, cid)
                await _safe_send(
                    conn,
                    {"type": "subscribed", "conversation_id": str(cid)},
                )
                continue

            if mtype == "unsubscribe":
                if msg.get("delivery_order_id") is not None:
                    try:
                        oid = uuid.UUID(msg["delivery_order_id"])
                    except (ValueError, TypeError):
                        continue
                    await _registry.unsubscribe_delivery(conn, oid)
                    continue
                cid_str = msg.get("conversation_id")
                if not cid_str:
                    continue
                try:
                    cid = uuid.UUID(cid_str)
                except ValueError:
                    continue
                await _registry.unsubscribe(conn, cid)
                continue

            if mtype == "typing":
                cid_str = msg.get("conversation_id")
                state = msg.get("state")
                if state not in ("start", "stop") or not cid_str:
                    continue
                try:
                    cid = uuid.UUID(cid_str)
                except ValueError:
                    continue
                if cid not in conn.conversations:
                    continue
                event = {
                    "type": "typing",
                    "conversation_id": str(cid),
                    "state": state,
                    "from": str(user.id),
                }
                # Broadcast to OTHER subscribers only.
                subs = await _registry.subscribers_of(cid)
                text = json.dumps(event, default=_json_default)
                for other in subs:
                    if other.user_id == user.id:
                        continue
                    try:
                        await other.ws.send_text(text)
                    except Exception:  # noqa: BLE001
                        pass
                continue

            await _safe_send(conn, {"type": "error", "error": "unknown_type"})
    finally:
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except (asyncio.CancelledError, Exception):  # noqa: BLE001
            pass
        await _registry.disconnect_all(conn)
        try:
            if ws.application_state != WebSocketState.DISCONNECTED:
                await ws.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            from app.core.observability import ws_connections_active
            ws_connections_active.dec()
        except Exception:  # noqa: BLE001
            pass


async def _safe_send(conn: WSConnection, event: dict[str, Any]) -> None:
    try:
        await conn.ws.send_text(json.dumps(event, default=_json_default))
    except Exception:  # noqa: BLE001
        pass


async def _heartbeat(conn: WSConnection) -> None:
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL_SECONDS)
            try:
                await conn.ws.send_text(json.dumps({"type": "ping"}))
            except Exception:  # noqa: BLE001
                return
    except asyncio.CancelledError:
        return
