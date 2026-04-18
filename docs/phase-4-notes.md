# Phase 4 — Backend B (sellers, stores, products) — Implementation Notes

## Endpoints added

All endpoints live under `/api/v1` and are included in the OpenAPI spec
(`/openapi.json`).  Tags: `sellers`, `stores`, `products`.

### Sellers

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/sellers/me` | seller | Returns the caller's seller profile (city, bio, country). |
| GET | `/sellers/me/dashboard` | seller | Lifetime + active-order aggregates (see below). |
| GET | `/sellers/{id}` | authenticated | admin: any; seller: self only; customer: only direct referring seller; driver: 404. |
| GET | `/sellers/{id}/dashboard` | admin | Admin view of any seller's dashboard. |

### Stores

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/stores` | seller | One store per seller — second POST returns 409 `STORE_ALREADY_EXISTS`.  `city` is required. Rate-limited 10/min. |
| GET | `/stores/me` | seller | 404 if no store yet. |
| PATCH | `/stores/me` | seller | Partial update (name, description, city, is_active). |
| GET | `/stores/{id}` | authenticated | admin: any; seller: self only; customer: only direct referring seller's store (404 otherwise — see ADR-0007); driver: 404. |

### Products

| Method | Path | Auth | Notes |
|---|---|---|---|
| POST | `/products` | seller | Seller must have a store.  Image metadata accepted inline. Rate-limited 60/min. |
| GET | `/products` | authenticated | Visibility-scoped list (admin: any; seller: own only; customer: only direct referring seller; driver: empty). |
| GET | `/products/{id}` | authenticated | Same visibility rules as list.  404 on non-visible or soft-deleted product (don't leak existence). |
| PATCH | `/products/{id}` | seller (own) / admin | Partial update; `images` field replaces the set wholesale if provided. |
| DELETE | `/products/{id}` | seller (own) / admin | Soft delete — sets `deleted_at` + `is_active=False`. |

## Key decisions

1. **`city` lives on `sellers.city`**, not a duplicated `stores.city`
   column.  The store endpoints accept `city` in the body and persist it
   to the seller profile (ADR-0010).  No schema change required.
2. **Dashboard lifetime metrics read directly from
   `order_analytics_snapshots`** (not from `seller_sales_rollups`).  This
   guarantees correctness without depending on a not-yet-built nightly
   refresh job, and leverages the snapshot table's
   no-foreign-keys-by-design property so numbers persist across order
   hard-delete and product soft-delete (ADR-0010).
3. **Customer visibility denial returns 404, not 403**
   (ADR-0007).  The `VisibilityDenied` exception maps to HTTP 404 via
   subclassing `NotFoundError`.  This prevents customers from
   enumerating sellers or stores they aren't linked to.
4. **Cross-seller lookups also return 404**, for the same reason:
   Seller B attempting to GET/PATCH/DELETE Seller A's resource gets 404,
   not 403, so Seller B can't discover Seller A's product IDs by probing.
5. **Drivers cannot browse the customer catalog.** `/products` returns
   an empty list for drivers; `/products/{id}` and `/stores/{id}` return
   404.  No driver-specific endpoints exist in this phase.
6. **Ownership is enforced at the service layer** via
   `product.seller_id == caller_seller.id`.  Admins bypass the check.
7. **Soft-delete semantics**: `soft_delete_product` sets both
   `deleted_at` and `is_active=False`.  Queries in the service layer
   exclude soft-deleted rows; order-history rows keep
   `product_name_snapshot` / `unit_price_minor_snapshot` from Phase 2.
8. **Image metadata** is accepted inline on create/update.  No upload
   pre-signed URL endpoint this phase — that's Phase 6+.  PATCH with
   `images` present replaces the entire set; omitting `images` leaves
   them unchanged.
9. **Typed exceptions added** to `app/core/exceptions.py`:
   `StoreAlreadyExists` (409), `StoreCityRequired` (422),
   `StoreNotFound` (404), `ProductNotFound` (404),
   `ProductOwnershipError` (403), `VisibilityDenied` (404 — subclass
   of `NotFoundError`), `SellerNotFound` (404),
   `SellerProfileMissing` (400).
10. **Rate limits**: POST /stores 10/min, POST /products 60/min.  Phase
    12 will harden with Redis-backed limits per ADR follow-ups.

## Visibility rule implementation approach

The rule (ADR-0007, depth=1) lives in two service layers:

- `product_service.get_product_for_caller` / `list_products_for_caller`
  branch on `caller.role`:
  - `admin`: no filter.
  - `seller`: filter by the caller's `Seller.id`.
  - `customer`: filter by `caller.referring_seller_id`; returns `[]` /
    404 if that field is NULL.
  - `driver` / anything else: returns `[]` / 404.
- `store_service.get_store_for_caller` applies the same branching on
  `store.seller_id`.

Customers whose `referring_seller_id` is NULL (admin-invited, per
ADR-0007) see nothing; Phase 11 will add an admin-managed override per
that ADR.

## Dashboard persistence guarantee

`seller_service.get_dashboard` issues exactly one `SUM` + `COUNT` against
`order_analytics_snapshots` filtered by `seller_id`.  Because that table
has zero foreign keys (Phase 2 design), the numbers persist through:

- product soft-delete (tested in `test_dashboard.py::test_lifetime_sales_survive_product_soft_delete`);
- order hard-delete (tested in `test_dashboard.py::test_lifetime_sales_survive_order_hard_delete`).

`active_orders_count` is a separate `COUNT(*) WHERE status IN ('pending',
'accepted', 'preparing', 'out_for_delivery')` against `orders` and is
computed live on each read (tested across state transitions in
`test_dashboard.py::test_active_orders_count_transitions`).

## Files added

```
backend/app/schemas/sellers.py
backend/app/schemas/stores.py
backend/app/schemas/products.py
backend/app/services/seller_service.py
backend/app/services/store_service.py
backend/app/services/product_service.py
backend/app/api/v1/sellers.py
backend/app/api/v1/stores.py
backend/app/api/v1/products.py
backend/tests/test_stores.py       (15 tests)
backend/tests/test_products.py     (12 tests)
backend/tests/test_visibility.py   (8 tests)
backend/tests/test_dashboard.py    (7 tests)
docs/adr/0010-phase-4-store-city-and-dashboard-source.md
docs/phase-4-notes.md
```

Files modified:

```
backend/app/main.py                # register 3 new routers
backend/app/core/exceptions.py     # Phase-4 domain exceptions
backend/tests/conftest.py          # seed helpers + path fix for cwd
```

No Alembic migration is required; Phase 2 already shipped every table
and column Phase 4 touches.
