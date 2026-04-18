"""FastAPI dependency functions for auth, database sessions, and RBAC.

Usage:
    from app.api.deps import get_current_user, require_roles

    @router.get("/protected")
    async def endpoint(user: User = Depends(get_current_user)):
        ...

    get_current_admin = require_roles("admin")

    @router.get("/admin-only")
    async def admin_endpoint(user: User = Depends(get_current_admin)):
        ...
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Callable
from typing import Optional

import sqlalchemy as sa
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import AuthenticationError, AuthorizationError, InvalidTokenError
from app.core.security import decode_access_token
from app.db.session import AsyncSessionFactory
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

# ---------------------------------------------------------------------------
# Database session dependency
# ---------------------------------------------------------------------------

_bearer = HTTPBearer(auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session per request.

    Commits on clean exit, rolls back on exception.
    """
    async with AsyncSessionFactory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode the Bearer JWT, load the User, and return it.

    Raises AuthenticationError (401) if:
    - No token provided.
    - Token is invalid or expired.
    - User not found, disabled, or soft-deleted.
    """
    if credentials is None:
        raise AuthenticationError("Authentication required.", code="AUTH_TOKEN_INVALID")

    try:
        payload = decode_access_token(credentials.credentials)
    except (AuthenticationError, InvalidTokenError, Exception) as exc:
        if isinstance(exc, AuthenticationError):
            raise
        raise AuthenticationError("Token is invalid.") from exc

    result = await db.execute(
        sa.select(User).where(
            User.id == payload.sub,  # type: ignore[arg-type]
            User.deleted_at.is_(None),
        )
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise AuthenticationError("Authentication required.", code="AUTH_TOKEN_INVALID")
    # Reject disabled accounts (is_active=False) and explicitly-disabled accounts
    # (disabled_at IS NOT NULL).  Both map to the same opaque 401.
    if not user.is_active or user.disabled_at is not None:
        raise AuthenticationError("Authentication required.", code="AUTH_TOKEN_INVALID")

    return user


async def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> Optional[User]:
    """Like get_current_user but returns None if no token is present.

    Provided for Phase 4+ endpoints where auth is optional.
    """
    if credentials is None:
        return None
    try:
        return await get_current_user(credentials, db)
    except AuthenticationError:
        return None


# ---------------------------------------------------------------------------
# RBAC factory
# ---------------------------------------------------------------------------


def require_roles(*roles: str) -> Callable[..., User]:
    """Factory returning a FastAPI dependency that enforces role membership.

    Usage::

        get_current_admin = require_roles("admin")

        @router.post("/admin-only")
        async def endpoint(user: User = Depends(get_current_admin)):
            ...
    """
    role_set = frozenset(roles)

    async def _dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in role_set:
            raise AuthorizationError(
                f"Role {user.role!r} is not authorized for this endpoint. "
                f"Required: {sorted(role_set)}."
            )
        return user

    return _dep  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Pre-built role dependencies
# ---------------------------------------------------------------------------

get_current_admin = require_roles("admin")
get_current_seller_or_admin = require_roles("seller", "admin")
