"""Test configuration and fixtures.

Strategy:
- Session-scoped sync: create marketplace_test DB, run alembic upgrade head.
- Function-scoped async: per-test AsyncEngine + full transaction rollback for isolation.
- AsyncClient via httpx + ASGITransport, with get_db dep overridden.
- seed_admin() / seed_seller_with_profile() helpers.

NOTE: Each test gets its own engine/connection to avoid event-loop
cross-contamination with SlowAPIMiddleware (BaseHTTPMiddleware uses a new
task per request, which must share the same loop as the engine).
"""

from __future__ import annotations

# -- Must run before any ``app.*`` import so the engine binds to the test DB --
import os as _os

TEST_DB_URL = (
    "postgresql+asyncpg://marketplace:marketplace@localhost:5432/marketplace_test"
)
TEST_DB_SYNC_URL = (
    "postgresql://marketplace:marketplace@localhost:5432/marketplace_test"
)
_os.environ.setdefault("APP_DATABASE_URL", TEST_DB_URL)
_os.environ.setdefault("APP_DATABASE_URL_SYNC", TEST_DB_SYNC_URL)

import subprocess
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.security import hash_password
from app.main import app
from app.models.user import User


# ---------------------------------------------------------------------------
# Session-scoped sync: create test DB and run migrations
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _disable_rate_limiter() -> Any:
    """Disable the SlowAPI limiter for the test session.

    Phase 6 adds many more HTTP calls per session; the 10/minute login
    limit now gets exceeded.  Individual tests re-enable it locally via
    ``monkeypatch.setattr(rate_limiter.limiter, "enabled", True)``.
    """
    from app.core import rate_limiter

    rate_limiter.limiter.enabled = False
    yield
    rate_limiter.limiter.enabled = True


@pytest.fixture(scope="session", autouse=True)
def setup_test_db() -> Any:
    """Drop and recreate marketplace_test, then run alembic upgrade head."""
    import psycopg2  # type: ignore[import-untyped]

    # Connect to the default `postgres` admin DB to issue DROP/CREATE. Do NOT
    # connect to a named app DB here — on CI the service container only creates
    # `marketplace_test` (the one we're about to drop/recreate), so connecting
    # to `marketplace` would fail with "database does not exist". The `postgres`
    # DB is always present on any postgres instance.
    conn = psycopg2.connect(
        "postgresql://marketplace:marketplace@localhost:5432/postgres"
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute(
        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
        "WHERE datname = 'marketplace_test' AND pid <> pg_backend_pid()"
    )
    cur.execute("DROP DATABASE IF EXISTS marketplace_test")
    cur.execute("CREATE DATABASE marketplace_test")
    cur.close()
    conn.close()

    import os
    from pathlib import Path

    env = os.environ.copy()
    env["APP_DATABASE_URL"] = TEST_DB_URL
    env["APP_DATABASE_URL_SYNC"] = TEST_DB_SYNC_URL
    backend_dir = Path(__file__).resolve().parent.parent
    subprocess.run(
        ["python", "-m", "alembic", "upgrade", "head"],
        cwd=str(backend_dir),
        env=env,
        check=True,
        capture_output=True,
    )
    yield


# ---------------------------------------------------------------------------
# Function-scoped: per-test engine + full rollback
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def db() -> AsyncGenerator[AsyncSession, None]:
    """Per-test async session with transaction rollback for isolation.

    Creates a fresh engine per test so that asyncpg connections share the
    same event loop as the test coroutine (avoids 'attached to a different
    loop' errors from BaseHTTPMiddleware task spawning).
    """
    engine = create_async_engine(
        TEST_DB_URL,
        echo=False,
        poolclass=NullPool,  # No pooling — each test gets a fresh connection in its own event loop
    )
    try:
        async with engine.connect() as conn:
            await conn.begin()

            session_factory = async_sessionmaker(
                bind=conn,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=False,
                autocommit=False,
            )

            async with session_factory() as session:
                yield session

            await conn.rollback()
    finally:
        await engine.dispose()


# ---------------------------------------------------------------------------
# HTTP client with overridden get_db dependency
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture()
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient using ASGITransport; get_db overridden to use test session."""
    from app.api.deps import get_db

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def seed_admin(db: AsyncSession, email: str = "admin_test@example.com") -> User:
    """Create an admin user directly (no invite required)."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("AdminPass123!"),
        role="admin",
        display_name="Test Admin",
        phone=None,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_seller_with_profile(
    db: AsyncSession, email: str = "seller_test@example.com"
) -> User:
    """Create a seller user with a sellers row."""
    from app.models.seller import Seller

    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("SellerPass123!"),
        role="seller",
        display_name="Test Seller",
        phone=None,
        is_active=True,
    )
    db.add(user)
    await db.flush()

    seller = Seller(
        id=user.id,
        user_id=user.id,
        display_name="Test Seller",
        bio=None,
        city="TestCity",
        country_code="US",
    )
    db.add(seller)
    await db.flush()

    return user


async def create_admin_invite(
    db: AsyncSession,
    issuer: User,
    role_target: str,
    *,
    expired: bool = False,
    revoked: bool = False,
    used: bool = False,
) -> str:
    """Create an admin invite and return the plaintext token."""
    import secrets
    from datetime import timedelta

    from app.models.invite_link import InviteLink

    plaintext = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    expires_at = (
        now - timedelta(hours=1) if expired else now + timedelta(hours=168)
    )

    invite = InviteLink(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        type="admin_invite",
        token=plaintext,
        role_target=role_target,
        max_uses=1,
        used_count=1 if used else 0,
        expires_at=expires_at,
        revoked_at=now if revoked else None,
    )
    db.add(invite)
    await db.flush()
    return plaintext


async def seed_customer(
    db: AsyncSession,
    email: str = "customer_test@example.com",
    *,
    referring_seller_id: uuid.UUID | None = None,
) -> User:
    """Create a customer user (optionally linked to a referring seller)."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("CustomerPass123!"),
        role="customer",
        display_name="Test Customer",
        phone=None,
        is_active=True,
        referring_seller_id=referring_seller_id,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_driver(
    db: AsyncSession,
    email: str = "driver_test@example.com",
) -> User:
    """Create a driver user."""
    user = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password("DriverPass123!"),
        role="driver",
        display_name="Test Driver",
        phone=None,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    return user


async def seed_store_for_seller(
    db: AsyncSession,
    seller_user: User,
    *,
    name: str = "Test Store",
    slug: str | None = None,
) -> Any:
    """Create a Store row directly for a seller user."""
    from app.models.store import Store

    store = Store(
        id=uuid.uuid4(),
        seller_id=seller_user.id,
        name=name,
        slug=slug or f"store-{uuid.uuid4().hex[:8]}",
        description="",
        is_active=True,
    )
    db.add(store)
    await db.flush()
    return store


async def seed_product(
    db: AsyncSession,
    seller_user: User,
    store: Any,
    *,
    name: str = "Test Product",
    price_minor: int = 1000,
    stock_quantity: int | None = 10,
) -> Any:
    """Create a Product row directly."""
    from app.models.product import Product

    product = Product(
        id=uuid.uuid4(),
        seller_id=seller_user.id,
        store_id=store.id,
        name=name,
        description="",
        price_minor=price_minor,
        stock_quantity=stock_quantity,
        is_active=True,
    )
    db.add(product)
    await db.flush()
    return product


async def create_seller_referral(
    db: AsyncSession,
    issuer: User,
    *,
    revoked: bool = False,
) -> str:
    """Create a seller referral invite and return the plaintext token."""
    import secrets

    from app.models.invite_link import InviteLink

    plaintext = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)

    invite = InviteLink(
        id=uuid.uuid4(),
        issuer_id=issuer.id,
        type="seller_referral",
        token=plaintext,
        role_target=None,
        max_uses=None,
        used_count=0,
        expires_at=None,
        revoked_at=now if revoked else None,
    )
    db.add(invite)
    await db.flush()
    return plaintext
