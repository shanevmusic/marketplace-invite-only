"""Development seed script.

Populates the database with a minimal dataset for local development and
integration testing.

Usage:
    cd /backend
    python -m app.scripts.seed_dev

Idempotent: if ``admin@example.com`` already exists the script logs a message
and exits with code 0.  Re-running after a fresh DB will always seed cleanly.

Seed users (password for all: ``DevPass123!``):
  - admin@example.com  / role=admin
  - seller@example.com / role=seller  → seller + store + 3 products
  - customer@example.com / role=customer (referred by seller)
  - driver@example.com / role=driver

Also creates:
  - A seller_referral invite_link for the seller (token generated via
    secrets.token_urlsafe(32) and printed at the end of seed output)
  - A referral row linking seller → customer
  - Platform settings singleton (idempotent via ON CONFLICT).

Security note: the seller_referral token is generated randomly on first run
and printed once.  It is NOT a hardcoded constant; do not hardcode it.
"""

from __future__ import annotations

import asyncio
import logging
import secrets
import sys
import uuid
from datetime import UTC, datetime

from argon2 import PasswordHasher
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionFactory

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed_dev")

PH = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=2,
)
PASSWORD = "DevPass123!"


def _hash(password: str) -> str:
    return PH.hash(password)


async def _seed(session: AsyncSession) -> None:
    # ------------------------------------------------------------------ #
    # Idempotency guard                                                    #
    # ------------------------------------------------------------------ #
    from app.models.user import User

    result = await session.execute(
        select(User).where(User.email == "admin@example.com")
    )
    existing = result.scalar_one_or_none()
    if existing is not None:
        log.info("admin@example.com already exists — seed is already applied; exiting.")
        return

    # ------------------------------------------------------------------ #
    # 1. Admin user                                                        #
    # ------------------------------------------------------------------ #
    admin_id = uuid.uuid4()
    admin = User(
        id=admin_id,
        email="admin@example.com",
        password_hash=_hash(PASSWORD),
        role="admin",
        display_name="Platform Admin",
        is_active=True,
    )
    session.add(admin)

    # ------------------------------------------------------------------ #
    # 2. Seller user                                                       #
    # ------------------------------------------------------------------ #
    from app.models.seller import Seller
    from app.models.store import Store
    from app.models.product import Product

    seller_user_id = uuid.uuid4()
    seller_user = User(
        id=seller_user_id,
        email="seller@example.com",
        password_hash=_hash(PASSWORD),
        role="seller",
        display_name="Seed Seller",
        is_active=True,
    )
    session.add(seller_user)

    # Seller profile row (same UUID as user)
    seller = Seller(
        id=seller_user_id,
        user_id=seller_user_id,
        display_name="Seed Seller Shop",
        bio="A sample seller seeded for development.",
        city="New York",
        country_code="US",
    )
    session.add(seller)

    # Flush so seller FK is available for store
    await session.flush()

    # Store
    store_id = uuid.uuid4()
    store = Store(
        id=store_id,
        seller_id=seller_user_id,
        name="Seed Store",
        slug="seed-store",
        description="Sample store for development.",
        is_active=True,
    )
    session.add(store)

    await session.flush()

    # 3 products
    products_data = [
        ("Widget Alpha", "A fine widget.", 1500, 100),
        ("Gadget Beta", "A useful gadget.", 2999, 50),
        ("Thingamajig Gamma", "A mysterious thingamajig.", 499, None),  # unlimited
    ]
    product_ids = []
    for name, desc, price, stock in products_data:
        p = Product(
            id=uuid.uuid4(),
            seller_id=seller_user_id,
            store_id=store_id,
            name=name,
            description=desc,
            price_minor=price,
            stock_quantity=stock,
            is_active=True,
        )
        session.add(p)
        product_ids.append(p.id)

    # ------------------------------------------------------------------ #
    # 3. Invite link (seller_referral) for the seller                     #
    # ------------------------------------------------------------------ #
    from app.models.invite_link import InviteLink

    # Security: generate a random token — never hardcode invite tokens.
    seller_referral_token = secrets.token_urlsafe(32)

    invite_id = uuid.uuid4()
    invite = InviteLink(
        id=invite_id,
        issuer_id=seller_user_id,
        type="seller_referral",
        token=seller_referral_token,
        role_target=None,
        max_uses=None,
        used_count=1,  # will be used by customer below
        expires_at=None,
    )
    session.add(invite)

    # ------------------------------------------------------------------ #
    # 4. Customer user (referred by seller)                               #
    # ------------------------------------------------------------------ #
    from app.models.referral import Referral

    customer_id = uuid.uuid4()
    customer = User(
        id=customer_id,
        email="customer@example.com",
        password_hash=_hash(PASSWORD),
        role="customer",
        display_name="Seed Customer",
        is_active=True,
        referring_seller_id=seller_user_id,
    )
    session.add(customer)

    await session.flush()

    # Referral row
    referral = Referral(
        id=uuid.uuid4(),
        referrer_id=seller_user_id,
        referred_user_id=customer_id,
        invite_link_id=invite_id,
    )
    session.add(referral)

    # ------------------------------------------------------------------ #
    # 5. Driver user                                                       #
    # ------------------------------------------------------------------ #
    driver_id = uuid.uuid4()
    driver = User(
        id=driver_id,
        email="driver@example.com",
        password_hash=_hash(PASSWORD),
        role="driver",
        display_name="Seed Driver",
        is_active=True,
    )
    session.add(driver)

    # ------------------------------------------------------------------ #
    # 6. Platform settings (idempotent — migration already inserts row 1) #
    # ------------------------------------------------------------------ #
    await session.execute(
        text(
            """
            INSERT INTO platform_settings (id, retention_min_days, currency_code, updated_at)
            VALUES (1, 30, 'USD', now())
            ON CONFLICT (id) DO NOTHING
            """
        )
    )

    # ------------------------------------------------------------------ #
    # Commit                                                               #
    # ------------------------------------------------------------------ #
    await session.commit()

    # ------------------------------------------------------------------ #
    # Summary table                                                        #
    # ------------------------------------------------------------------ #
    log.info("Seed complete.")
    print("\n" + "=" * 72)
    print(f"{'Email':<30} {'Role':<10} {'ID'}")
    print("-" * 72)
    rows = [
        (admin.email, admin.role, str(admin.id)),
        (seller_user.email, seller_user.role, str(seller_user.id)),
        (customer.email, customer.role, str(customer.id)),
        (driver.email, driver.role, str(driver.id)),
    ]
    for email, role, uid in rows:
        print(f"{email:<30} {role:<10} {uid}")
    print("=" * 72)
    print(f"\nStore   : {store.name!r} (slug={store.slug!r})")
    print(f"Products: {len(product_ids)} seeded")
    print(f"Seller referral token: {seller_referral_token}")
    print()


async def _seed_moderation_samples(session: AsyncSession) -> None:
    """Optional: seed one suspended user + one disabled product for admin demo."""
    from datetime import datetime, timezone

    from app.models.product import Product
    from app.models.user import User

    # Suspend driver@example.com
    driver = (
        await session.execute(
            select(User).where(User.email == "driver@example.com")
        )
    ).scalar_one_or_none()
    if driver is not None and driver.status != "suspended":
        driver.status = "suspended"
        driver.suspended_at = datetime.now(timezone.utc)
        driver.suspended_reason = "Demo: TOS violation (seed moderation sample)"

    # Disable the first product.
    product = (
        await session.execute(select(Product).order_by(Product.created_at).limit(1))
    ).scalar_one_or_none()
    if product is not None and product.status != "disabled":
        product.status = "disabled"
        product.disabled_at = datetime.now(timezone.utc)
        product.disabled_reason = "Demo: flagged (seed moderation sample)"

    await session.commit()
    log.info("Seeded moderation samples (suspended driver + disabled product).")


async def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--with-moderation-samples",
        action="store_true",
        help="After base seed, suspend driver + disable one product for admin demo.",
    )
    args = parser.parse_args()

    async with AsyncSessionFactory() as session:
        await _seed(session)

    if args.with_moderation_samples:
        async with AsyncSessionFactory() as session:
            await _seed_moderation_samples(session)


if __name__ == "__main__":
    asyncio.run(main())
