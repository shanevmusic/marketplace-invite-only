"""Push-notification service (Phase 12 — workstream f).

Scaffolding with pluggable backends.  Real delivery via FCM / APNs is
wired behind config flags; when credentials are absent the service
no-ops and logs at INFO so dev/test environments don't require real
push credentials.

Public entrypoint:

    await send_notification(db, user_id, title, body, data=None)

The function is safe to invoke from a FastAPI ``BackgroundTasks`` callback
or via ``asyncio.create_task`` — it does not raise on transport errors,
logging them instead.  Callers should NOT await critical business logic
on the push result.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.user_device import UserDevice

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Notification:
    user_id: uuid.UUID
    title: str
    body: str
    data: dict[str, str] | None = None


class Sender(Protocol):
    async def send(
        self,
        device: UserDevice,
        notification: Notification,
    ) -> bool:  # True on success, False on permanent failure
        ...


class _NoopSender:
    """Default sender used when no real credentials are configured."""

    def __init__(self, reason: str) -> None:
        self._reason = reason

    async def send(
        self,
        device: UserDevice,
        notification: Notification,
    ) -> bool:
        _logger.info(
            "push.noop platform=%s user_id=%s reason=%s title=%r",
            device.platform,
            device.user_id,
            self._reason,
            notification.title,
        )
        return True


class _FCMSender:
    """FCM legacy HTTP v1 sender (stub — uses ``httpx`` when wired)."""

    def __init__(self, server_key: str) -> None:
        self._server_key = server_key

    async def send(
        self,
        device: UserDevice,
        notification: Notification,
    ) -> bool:  # pragma: no cover - network-integrated path
        try:
            import httpx  # local import to keep the module light
        except Exception as exc:
            _logger.warning("push.fcm httpx import failed: %s", exc)
            return True

        payload = {
            "to": device.token,
            "notification": {
                "title": notification.title,
                "body": notification.body,
            },
            "data": notification.data or {},
        }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    "https://fcm.googleapis.com/fcm/send",
                    headers={
                        "Authorization": f"key={self._server_key}",
                        "Content-Type": "application/json",
                    },
                    content=json.dumps(payload),
                )
            if resp.status_code == 200:
                return True
            _logger.warning("push.fcm status=%s body=%s", resp.status_code, resp.text)
            # 4xx on token == permanent failure.
            return resp.status_code >= 500
        except Exception as exc:
            _logger.warning("push.fcm transport error: %s", exc)
            return True


class _APNsSender:
    """APNs HTTP/2 sender (stub — real impl via aioapns in Phase 13)."""

    def __init__(self, team_id: str, key_id: str, bundle_id: str, key_pem: str) -> None:
        self._team_id = team_id
        self._key_id = key_id
        self._bundle_id = bundle_id
        self._key_pem = key_pem

    async def send(
        self,
        device: UserDevice,
        notification: Notification,
    ) -> bool:  # pragma: no cover
        _logger.info(
            "push.apns stub platform=%s user_id=%s title=%r",
            device.platform,
            device.user_id,
            notification.title,
        )
        return True


def _pick_sender(platform: str) -> Sender:
    if platform == "android" and settings.fcm_server_key:
        return _FCMSender(settings.fcm_server_key)
    if platform == "ios" and settings.apns_key_pem and settings.apns_team_id:
        return _APNsSender(
            team_id=settings.apns_team_id,
            key_id=settings.apns_key_id,
            bundle_id=settings.apns_bundle_id,
            key_pem=settings.apns_key_pem,
        )
    return _NoopSender(reason="push-not-configured")


async def _load_devices(db: AsyncSession, user_id: uuid.UUID) -> list[UserDevice]:
    result = await db.execute(
        sa.select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.disabled_at.is_(None),
        )
    )
    return list(result.scalars())


async def send_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    title: str,
    body: str,
    data: Optional[dict[str, str]] = None,
) -> None:
    """Fan-out a notification to every active device of *user_id*.

    Non-raising: transport errors are logged.  Permanent-failure tokens
    (4xx from FCM) get ``disabled_at`` stamped so we stop retrying them.
    """
    devices = await _load_devices(db, user_id)
    if not devices:
        return

    notification = Notification(user_id=user_id, title=title, body=body, data=data)

    async def _send_one(device: UserDevice) -> None:
        sender = _pick_sender(device.platform)
        try:
            ok = await sender.send(device, notification)
        except Exception as exc:  # pragma: no cover
            _logger.warning("push.send_one error: %s", exc)
            ok = True
        if not ok:
            device.disabled_at = datetime.now(timezone.utc)
        else:
            device.last_seen_at = datetime.now(timezone.utc)

    await asyncio.gather(*(_send_one(d) for d in devices))
    await db.flush()


async def register_device(
    db: AsyncSession,
    user_id: uuid.UUID,
    platform: str,
    token: str,
) -> UserDevice:
    """Idempotent upsert of a device registration."""
    if platform not in ("ios", "android", "web"):
        from app.core.exceptions import ValidationError

        raise ValidationError("platform must be one of ios|android|web.")

    result = await db.execute(
        sa.select(UserDevice).where(
            UserDevice.user_id == user_id,
            UserDevice.token == token,
        )
    )
    existing = result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing is not None:
        existing.platform = platform
        existing.disabled_at = None
        existing.last_seen_at = now
        await db.flush()
        return existing

    device = UserDevice(
        id=uuid.uuid4(),
        user_id=user_id,
        platform=platform,
        token=token,
        last_seen_at=now,
    )
    db.add(device)
    await db.flush()
    return device
