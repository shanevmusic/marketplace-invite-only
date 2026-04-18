"""Auth router — signup, login, refresh, logout, me.

Rate limits (slowapi):
- POST /signup:  5/min per IP
- POST /login:  10/min per IP
- POST /refresh: 30/min per IP
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.core.exceptions import AuthenticationError
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    MeResponse,
    RefreshRequest,
    RefreshResponse,
    SignupRequest,
)
from app.services import auth_service
from app.core.rate_limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# POST /auth/signup
# ---------------------------------------------------------------------------


@router.post("/signup", response_model=LoginResponse, status_code=201)
@limiter.limit("3/minute")
async def signup(
    request: Request,  # required by slowapi
    body: SignupRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Create a new user account. Requires a valid invite token."""
    return await auth_service.signup(db, body)


# ---------------------------------------------------------------------------
# POST /auth/login
# ---------------------------------------------------------------------------


@router.post("/login", response_model=LoginResponse, status_code=200)
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """Authenticate with email + password and receive a token pair."""
    return await auth_service.login(
        db,
        email=str(body.email),
        password=body.password,
        device_label=body.device_label,
    )


# ---------------------------------------------------------------------------
# POST /auth/refresh
# ---------------------------------------------------------------------------


@router.post("/refresh", response_model=RefreshResponse, status_code=200)
@limiter.limit("30/minute")
async def refresh_token(
    request: Request,
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> RefreshResponse:
    """Rotate a refresh token and receive a new token pair."""
    return await auth_service.refresh(db, body.refresh_token)


# ---------------------------------------------------------------------------
# POST /auth/logout
# ---------------------------------------------------------------------------


@router.post("/logout", status_code=204)
async def logout(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> Response:
    """Revoke the presented refresh token. Returns 204 No Content."""
    await auth_service.logout(db, body.refresh_token)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# POST /auth/logout_all
# ---------------------------------------------------------------------------


@router.post("/logout_all", status_code=204)
async def logout_all(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> Response:
    """Revoke ALL refresh tokens for the authenticated user."""
    await auth_service.logout_all(db, user)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# GET /auth/me
# ---------------------------------------------------------------------------


@router.get("/me", response_model=MeResponse)
async def get_me(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> MeResponse:
    """Return the authenticated user's profile."""
    fresh = await auth_service.get_me(db, user)
    return MeResponse(
        id=fresh.id,
        email=fresh.email,
        role=fresh.role,
        display_name=fresh.display_name,
        phone=fresh.phone,
        is_active=fresh.is_active,
        created_at=fresh.created_at,
        referring_seller_id=fresh.referring_seller_id,
    )
