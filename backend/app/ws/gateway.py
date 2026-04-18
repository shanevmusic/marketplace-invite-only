"""WebSocket gateway — in-process fanout for conversation events.

This gateway is the minimal single-process pub/sub for Phase 6. A Redis
pub/sub is the Phase 12 upgrade for multi-node deployment.

Close codes:
- 4401 — missing/invalid/expired JWT at handshake or during session.
- 4403 — caller is not a participant of the conversation they tried to join.

Events sent from server to clients:
- ``message.new``  — full ciphertext payload for a new message.
- ``message.read`` — read-receipt for a message the recipient marked read.
- ``typing``       — {"type":"typing","conversation_id","state":"start"|"stop","from":<user_id>}

Client → server messages (JSON):
- ``{"type":"subscribe","conversation_id":"..."}``
- ``{"type":"unsubscribe","conversation_id":"..."}``
- ``{"type":"typing","conversation_id":"...","state":"start"|"stop"}``
- ``{"type":"ping"}``   — client-initiated; server replies with ``{"type":"pong"}``.

Server-initiated ping every 30s; connection dropped if no traffic.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

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


# ---------------------------------------------------------------------------
# Connection registry
# ---------------------------------------------------------------------------


@dataclass(eq=False)
class WSConnection:
    """Identity-equal dataclass so instances are hashable for set membership."""

    ws: WebSocket
    user_id: uuid.UUID
    conversations: set[uuid.UUID] = field(default_factory=set)

    def __hash__(self) -> int:
        return id(self)


class ConnectionRegistry:
    """Thread-safe (single-event-loop) fanout registry."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        # conversation_id -> set of connections subscribed
        self._subs: dict[uuid.UUID, set[WSConnection]] = {}

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

    async def disconnect_all(self, conn: WSConnection) -> None:
        async with self._lock:
            for cid in list(conn.conversations):
                subs = self._subs.get(cid)
                if subs is not None:
                    subs.discard(conn)
                    if not subs:
                        del self._subs[cid]
            conn.conversations.clear()

    async def subscribers_of(
        self, conversation_id: uuid.UUID
    ) -> list[WSConnection]:
        async with self._lock:
            return list(self._subs.get(conversation_id, set()))


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


async def _broadcast_event(
    conversation_id: uuid.UUID, event: dict[str, Any]
) -> None:
    subs = await _registry.subscribers_of(conversation_id)
    if not subs:
        return
    text = json.dumps(event, default=_json_default)
    for conn in subs:
        try:
            await conn.ws.send_text(text)
        except Exception:  # noqa: BLE001
            logger.debug("drop broadcast to dead socket user=%s", conn.user_id)


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
    conn = WSConnection(ws=ws, user_id=user.id)

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
