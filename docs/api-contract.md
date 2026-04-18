# API Contract — Invite-Only Marketplace

> **Phase 1 deliverable.** Summarizes conventions and freezes the skeleton for backend scaffolding. The authoritative source once the backend is running is the FastAPI-generated OpenAPI at `/openapi.json`. This document governs **breaking-change rules** (§10). See [PROJECT.md](../PROJECT.md) §5.2 for naming conventions and [architecture.md](architecture.md) for service context.

---

## 1. API Conventions

### 1.1 Versioning

All REST endpoints are prefixed with `/api/v1/`. When a breaking change is required, a new prefix `/api/v2/` is introduced; the old version is deprecated (not deleted) for at least one minor release cycle. WebSocket namespaces follow `/ws/v1/{feature}`.

### 1.2 Authentication Header

```
Authorization: Bearer <access_token>
```

Access tokens are JWTs (15 min TTL). Clients obtain new access tokens using the refresh endpoint. Unauthenticated endpoints are explicitly marked `public` in the tables below.

### 1.3 Error Envelope

All error responses use a consistent JSON body:

```json
{
  "error": {
    "code": "INVITE_EXPIRED",
    "message": "The invite token has expired.",
    "detail": null
  }
}
```

`code` is a machine-readable string from the error codes table (§9). `detail` may contain field-level validation errors for 422 responses.

### 1.4 Pagination

List endpoints that can return large result sets use cursor-based pagination via query parameters:

```
GET /api/v1/products?cursor=<opaque_cursor>&limit=20
```

Response includes:

```json
{
  "data": [...],
  "pagination": {
    "next_cursor": "<opaque_cursor_or_null>",
    "has_more": true
  }
}
```

Default `limit` is 20; max is 100. Offset pagination is available for admin list endpoints only.

### 1.5 Idempotency Keys

Mutating endpoints that create resources or trigger external actions accept an optional `Idempotency-Key: <uuid>` header. The server caches the response for 24 hours keyed on `(user_id, idempotency_key)`. Applicable endpoints are marked *(idempotent)* below.

### 1.6 HTTP Status Usage

| Status | Meaning |
|---|---|
| 200 | Success (GET, PATCH, PUT) |
| 201 | Resource created (POST) |
| 204 | Success, no body (DELETE, logout) |
| 400 | Bad request / business rule violation |
| 401 | Missing or invalid auth token |
| 403 | Authenticated but insufficient role |
| 404 | Resource not found (or visibility-hidden) |
| 409 | Conflict (duplicate, already-used token) |
| 422 | Validation error (Pydantic) |
| 429 | Rate limit exceeded |
| 500 | Unexpected server error |

### 1.7 Common Fields

- All PKs are UUID v4, returned as lowercase hyphenated strings.
- Timestamps are ISO 8601 UTC strings: `"2024-01-15T10:30:00Z"`.
- Soft-deleted resources return 404 to non-admin callers.

---

## 2. Auth Endpoints

### POST /api/v1/auth/signup *(public, idempotent)*

Invite-bound signup. Requires a valid, unused invite token.

**Request:**
```json
{
  "invite_token": "string",
  "name": "string",
  "email": "string",
  "phone": "string (optional)",
  "password": "string (min 10 chars)"
}
```

**Response 201:**
```json
{
  "access_token": "string",
  "refresh_token": "string",
  "token_type": "bearer",
  "user": { "id": "uuid", "name": "string", "role": "customer|seller|driver" }
}
```

**Errors:** `INVITE_NOT_FOUND`, `INVITE_EXPIRED`, `INVITE_ALREADY_USED`, `EMAIL_TAKEN`

---

### POST /api/v1/auth/login *(public)*

**Request:**
```json
{ "email": "string", "password": "string" }
```

**Response 200:** Same shape as signup.

**Errors:** `INVALID_CREDENTIALS`, `RATE_LIMITED`

---

### POST /api/v1/auth/refresh *(public)*

**Request:**
```json
{ "refresh_token": "string" }
```

**Response 200:**
```json
{ "access_token": "string", "refresh_token": "string", "token_type": "bearer" }
```

Old refresh token is invalidated on use (rotation). **Errors:** `TOKEN_INVALID`, `TOKEN_EXPIRED`

---

### GET /api/v1/auth/me

Auth: any authenticated role.

**Response 200:**
```json
{ "id": "uuid", "name": "string", "email": "string", "role": "string", "created_at": "timestamp" }
```

---

### POST /api/v1/auth/logout

Auth: any authenticated role.

**Request:** (none — token taken from header)

**Response 204.** Invalidates the current refresh token server-side.

---

## 3. Invites Endpoints

### POST /api/v1/invites *(idempotent)*

Auth: `admin` (any role target) or `seller` (can invite `customer` or `seller` only).

**Request:**
```json
{
  "email": "string (optional)",
  "phone": "string (optional)",
  "role": "customer|seller|driver",
  "expires_in_hours": 72
}
```

**Response 201:**
```json
{
  "id": "uuid",
  "token": "string",
  "invite_url": "string (deep-link)",
  "role": "string",
  "expires_at": "timestamp",
  "created_by": "uuid"
}
```

**Errors:** `FORBIDDEN` (seller trying to invite admin/driver), `RATE_LIMITED`

---

### GET /api/v1/invites/validate?token={token} *(public)*

Used by the Flutter deep-link handler before showing signup form.

**Response 200:**
```json
{
  "valid": true,
  "role": "customer",
  "inviter_name": "string",
  "expires_at": "timestamp"
}
```

**Errors:** `INVITE_NOT_FOUND`, `INVITE_EXPIRED`, `INVITE_ALREADY_USED`

---

### GET /api/v1/invites

Auth: `admin` (all), `seller` (own).

Returns list of invite_links created by the caller. Supports cursor pagination.

**Response 200:**
```json
{
  "data": [{ "id": "uuid", "role": "string", "used": false, "expires_at": "timestamp", "created_at": "timestamp" }],
  "pagination": { "next_cursor": "string|null", "has_more": false }
}
```

---

### DELETE /api/v1/invites/{id}

Auth: `admin` (any), `seller` (own only). Soft-revokes an unused invite.

**Response 204.** **Errors:** `INVITE_ALREADY_USED` (cannot revoke used invite)

---

## 4. Users Endpoints

### GET /api/v1/users/{id}

Auth: `admin` (any user), authenticated user (own record only).

**Response 200:**
```json
{
  "id": "uuid", "name": "string", "email": "string",
  "phone": "string|null", "role": "string",
  "created_at": "timestamp", "updated_at": "timestamp"
}
```

**Errors:** `NOT_FOUND`, `FORBIDDEN`

---

### PATCH /api/v1/users/{id}

Auth: own user (name, phone, password); `admin` (any field including role).

**Request (partial):**
```json
{ "name": "string", "phone": "string", "password": "string" }
```

**Response 200:** Updated user object.

---

## 5. Sellers / Stores Endpoints

### POST /api/v1/sellers

Auth: `admin` only. Creates a seller record for an existing user (role must be `seller`).

**Request:**
```json
{ "user_id": "uuid", "bio": "string (optional)" }
```

**Response 201:**
```json
{ "id": "uuid", "user_id": "uuid", "bio": "string|null", "created_at": "timestamp" }
```

---

### POST /api/v1/stores

Auth: `seller` (own). Creates the one store for the authenticated seller.

**Request:**
```json
{
  "name": "string",
  "city": "string",
  "description": "string (optional)",
  "address": "string (optional)"
}
```

**Response 201:**
```json
{ "id": "uuid", "seller_id": "uuid", "name": "string", "city": "string", "created_at": "timestamp" }
```

**Errors:** `STORE_ALREADY_EXISTS` (one store per seller)

---

### GET /api/v1/stores/{id}

Auth: `admin` (any store); `seller` (own); `customer` (only if referral chain includes this seller — returns 404 otherwise).

**Response 200:**
```json
{
  "id": "uuid", "seller_id": "uuid", "name": "string", "city": "string",
  "description": "string|null", "address": "string|null", "created_at": "timestamp"
}
```

---

### PATCH /api/v1/stores/{id}

Auth: `seller` (own).

**Request (partial):** `name`, `description`, `address`, `city`

**Response 200:** Updated store object.

---

### GET /api/v1/stores

Auth: `admin` only. Lists all stores across cities. Supports `?city={city}` filter and cursor pagination.

**Response 200:**
```json
{
  "data": [{ "id": "uuid", "name": "string", "city": "string", "seller_id": "uuid" }],
  "pagination": { "next_cursor": "string|null", "has_more": false }
}
```

---

### GET /api/v1/sellers/{id}/page

Public seller "page" as visible to a referred customer. Auth: `customer` (referral-scoped).

Returns store info + product summary; 404 if not in referral chain.

**Response 200:**
```json
{
  "store": { "id": "uuid", "name": "string", "city": "string", "description": "string|null" },
  "product_count": 12,
  "seller_name": "string"
}
```

---

## 6. Products Endpoints

### POST /api/v1/products *(idempotent)*

Auth: `seller`.

**Request:**
```json
{
  "store_id": "uuid",
  "name": "string",
  "description": "string (optional)",
  "price": "decimal string (e.g. \"9.99\")",
  "currency": "string (ISO 4217, e.g. \"USD\")",
  "stock": "integer"
}
```

**Response 201:**
```json
{ "id": "uuid", "store_id": "uuid", "name": "string", "price": "string", "stock": 50, "image_url": null, "created_at": "timestamp" }
```

---

### GET /api/v1/products/{id}

Auth: `seller` (own products); `customer` (referral-scoped); `admin` (any).

**Response 200:** Full product object including `image_url` (signed GET URL if image uploaded).

---

### PATCH /api/v1/products/{id}

Auth: `seller` (own). Partial update: `name`, `description`, `price`, `stock`.

**Response 200:** Updated product object.

---

### DELETE /api/v1/products/{id}

Auth: `seller` (own), `admin`. Soft-delete: sets `deleted_at`.

**Response 204.**

---

### GET /api/v1/products

Auth: `seller` (own store, `?store_id=`); `customer` (referral-scoped, requires `?store_id=`); `admin` (any, with `?store_id=` optional).

Cursor-paginated. Query params: `store_id`, `limit`, `cursor`.

**Response 200:**
```json
{
  "data": [{ "id": "uuid", "name": "string", "price": "string", "stock": 10, "image_url": "string|null" }],
  "pagination": { "next_cursor": "string|null", "has_more": false }
}
```

---

### POST /api/v1/products/{id}/image-upload-url

Auth: `seller` (own product).

Returns a pre-signed PUT URL for direct upload to S3/GCS. Client uploads the image file directly; backend is notified via a subsequent PATCH or a background webhook.

**Response 200:**
```json
{ "upload_url": "string (pre-signed PUT)", "expires_in_seconds": 300, "object_key": "string" }
```

---

## 7. Orders Endpoints

### POST /api/v1/orders *(idempotent)*

Auth: `customer`.

**Request:**
```json
{
  "store_id": "uuid",
  "items": [{ "product_id": "uuid", "quantity": 2 }],
  "delivery_address": "string",
  "notes": "string (optional)"
}
```

**Response 201:**
```json
{
  "id": "uuid", "store_id": "uuid", "customer_id": "uuid",
  "status": "pending", "total_amount": "string",
  "items": [{ "product_id": "uuid", "quantity": 2, "unit_price": "string" }],
  "created_at": "timestamp"
}
```

**Errors:** `STORE_NOT_IN_REFERRAL_CHAIN`, `INSUFFICIENT_STOCK`, `PRODUCT_NOT_FOUND`

---

### GET /api/v1/orders

Auth: `customer` (own orders); `seller` (orders for own store); `driver` (assigned orders); `admin` (all). Cursor-paginated. Query params: `status`, `store_id` (admin/seller).

**Response 200:**
```json
{
  "data": [{ "id": "uuid", "status": "string", "total_amount": "string", "created_at": "timestamp" }],
  "pagination": { "next_cursor": "string|null", "has_more": false }
}
```

---

### GET /api/v1/orders/{id}

Auth: parties to the order (customer, store's seller, assigned driver) + admin.

**Response 200:** Full order object with items, status, delivery info if exists.

---

### DELETE /api/v1/orders/{id}

Auth: `customer` (only if status=`pending`); `admin` (any status). Soft-cancel — sets `status=cancelled`. Hard-delete is handled by the background retention job only.

**Response 204.** **Errors:** `ORDER_NOT_CANCELLABLE`

---

### PATCH /api/v1/orders/{id}/accept

Auth: `seller` (own store order). Transitions `pending → accepted`.

**Response 200:** `{ "id": "uuid", "status": "accepted" }`

---

### PATCH /api/v1/orders/{id}/preparing

Auth: `seller`. Transitions `accepted → preparing`.

**Response 200:** `{ "id": "uuid", "status": "preparing" }`

---

### PATCH /api/v1/orders/{id}/start_delivery

Auth: `seller`. Transitions `preparing → out_for_delivery`. Creates `deliveries` record with seller as driver.

**Response 200:** `{ "id": "uuid", "status": "out_for_delivery", "delivery_id": "uuid" }`

---

### PATCH /api/v1/orders/{id}/request_driver

Auth: `seller`. Signals intent for admin-assigned driver. Sets internal flag; does not change order status yet.

**Response 200:** `{ "id": "uuid", "driver_requested": true }`

---

### PATCH /api/v1/orders/{id}/assign_driver *(admin)*

Auth: `admin`.

**Request:**
```json
{ "driver_id": "uuid" }
```

**Response 200:** `{ "id": "uuid", "status": "out_for_delivery", "delivery_id": "uuid" }`. Creates `deliveries` + `driver_assignments` records, notifies driver.

---

## 8. Deliveries Endpoints

### GET /api/v1/deliveries/{order_id}

Auth: customer (status/ETA only — lat/lng omitted from response); seller/driver (full); admin (full).

**Response 200 (customer view):**
```json
{
  "id": "uuid", "order_id": "uuid", "status": "in_progress",
  "eta_minutes": 12, "started_at": "timestamp", "delivered_at": null
}
```

**Response 200 (seller/driver/admin view):** Adds `current_lat`, `current_lng`.

---

### GET /api/v1/deliveries/{order_id}/metrics

Auth: `seller` (own), `admin`.

**Response 200:**
```json
{
  "started_at": "timestamp", "delivered_at": "timestamp|null",
  "duration_seconds": 720
}
```

---

### POST /api/v1/deliveries/{order_id}/location

Auth: `driver` (assigned) or `seller` (if self-delivering).

**Request:**
```json
{ "lat": 40.7128, "lng": -74.0060, "accuracy_meters": 5.0 }
```

**Response 200:** `{ "received": true }`. Publishes to Redis for WS fanout (see §11, asymmetric filter).

---

### PATCH /api/v1/deliveries/{order_id}/complete

Auth: `driver` or `seller`. Transitions order to `delivered`, sets `delivered_at`, triggers analytics snapshot.

**Response 200:** `{ "order_id": "uuid", "status": "delivered" }`

---

## 9. Messages (REST Fallback) Endpoints

WebSocket is the primary channel (§11). REST endpoints serve as fallback and for history loading.

### GET /api/v1/conversations

Auth: any authenticated role. Returns conversations where caller is a participant.

**Response 200:**
```json
{
  "data": [{
    "id": "uuid", "participant_ids": ["uuid", "uuid"],
    "last_message_at": "timestamp", "unread_count": 3
  }],
  "pagination": { "next_cursor": "string|null", "has_more": false }
}
```

---

### GET /api/v1/conversations/{id}/messages

Auth: conversation participant only.

Cursor-paginated (newest-first by default). Query params: `limit`, `cursor`, `direction=desc|asc`.

**Response 200:**
```json
{
  "data": [{
    "id": "uuid", "sender_id": "uuid",
    "ciphertext": "base64-string", "nonce": "base64-string",
    "ephemeral_public_key": "base64-string",
    "sent_at": "timestamp", "read_at": "timestamp|null"
  }],
  "pagination": { "next_cursor": "string|null", "has_more": false }
}
```

---

### POST /api/v1/conversations/{id}/messages *(idempotent)*

Auth: conversation participant.

**Request:**
```json
{
  "ciphertext": "base64-string",
  "nonce": "base64-string",
  "ephemeral_public_key": "base64-string"
}
```

**Response 201:** Full message object.

---

### POST /api/v1/conversations

Auth: any authenticated role. Creates a new 1:1 conversation.

**Request:**
```json
{ "participant_id": "uuid" }
```

**Response 201:** Conversation object. Returns existing conversation if one already exists between this pair (idempotent). **Errors:** `SELF_CONVERSATION`

---

### POST /api/v1/keys/register

Auth: any authenticated role. Registers or updates the caller's X25519 public key.

**Request:**
```json
{ "public_key": "base64-string" }
```

**Response 200:** `{ "registered": true }`

---

### GET /api/v1/keys/{user_id}

Auth: any authenticated role (to encrypt a message to a peer).

**Response 200:**
```json
{ "user_id": "uuid", "public_key": "base64-string", "registered_at": "timestamp" }
```

**Errors:** `KEY_NOT_REGISTERED`

---

## 10. Reviews Endpoints

Reviews are private (visible to admin and the seller's own view only — never shown publicly).

### POST /api/v1/orders/{order_id}/review *(idempotent)*

Auth: `customer` (must be order owner, order must be `delivered`).

**Request:**
```json
{ "rating": 4, "comment": "string (optional)" }
```

**Response 201:**
```json
{ "id": "uuid", "order_id": "uuid", "rating": 4, "comment": "string|null", "created_at": "timestamp" }
```

**Errors:** `ORDER_NOT_DELIVERED`, `REVIEW_ALREADY_EXISTS`

---

### GET /api/v1/reviews

Auth: `admin` (all reviews, `?seller_id=` filter); `seller` (own store's reviews). Private — not exposed to customers.

**Response 200:**
```json
{
  "data": [{ "id": "uuid", "order_id": "uuid", "rating": 4, "comment": "string|null", "created_at": "timestamp" }],
  "pagination": { "next_cursor": "string|null", "has_more": false }
}
```

---

## 11. Admin Endpoints

All endpoints in this group require `role = admin`.

### GET /api/v1/admin/users

List all users. Query params: `role`, `city`, `cursor`, `limit`.

**Response 200:** Paginated list of user objects (same shape as §4).

---

### PATCH /api/v1/admin/users/{id}

Update any user field (role, name, etc.).

**Request:** Partial user fields. **Response 200:** Updated user.

---

### DELETE /api/v1/admin/users/{id}

Soft-delete a user. Sets `deleted_at`; does not cascade-delete orders/messages (retention rules apply).

**Response 204.**

---

### GET /api/v1/admin/referral-graph

Returns the referral graph as a node-edge structure.

**Response 200:**
```json
{
  "nodes": [{ "id": "uuid", "name": "string", "role": "string" }],
  "edges": [{ "from": "uuid", "to": "uuid", "invite_id": "uuid", "created_at": "timestamp" }]
}
```

---

### GET /api/v1/admin/settings

**Response 200:**
```json
{ "platform_min_retention_days": 30, "updated_at": "timestamp" }
```

---

### PATCH /api/v1/admin/settings

**Request:**
```json
{ "platform_min_retention_days": 30 }
```

**Response 200:** Updated settings object.

---

## 12. Analytics Endpoints

### GET /api/v1/analytics/seller/summary

Auth: `seller` (own), `admin` (requires `?seller_id=`).

Returns lifetime sales metrics from `order_analytics_snapshots`. Cached in Redis (TTL 5 min).

**Response 200:**
```json
{
  "seller_id": "uuid",
  "total_orders_completed": 142,
  "lifetime_revenue": "14820.50",
  "currency": "USD",
  "period": "all_time",
  "last_updated": "timestamp"
}
```

---

## 13. WebSocket Endpoints

### 13.1 Connection Auth Flow

All WebSocket connections include the access token as a query parameter (since browsers cannot set custom headers in WS handshakes):

```
wss://api.example.com/ws/v1/messaging?token=<access_token>
wss://api.example.com/ws/v1/delivery/{order_id}?token=<access_token>
```

On connect, the server:
1. Validates the JWT (signature, expiry, role).
2. Registers the socket in the appropriate in-process connection pool.
3. Subscribes the worker process to the relevant Redis channel(s).
4. Sends a `connected` acknowledgment event.

On JWT expiry, the server sends a `auth.expired` event and closes the socket with code 4001. The client must reconnect with a refreshed token.

---

### 13.2 `/ws/v1/messaging`

**Auth:** any authenticated role.

Upon connection, the server subscribes the socket to all conversation channels where the user is a participant.

#### Events — Server → Client

| Event | Payload | Notes |
|---|---|---|
| `message.new` | `{ message_id, conversation_id, sender_id, ciphertext, nonce, ephemeral_public_key, sent_at }` | Sent to all participants of the conversation |
| `message.read` | `{ message_id, conversation_id, read_by, read_at }` | Sent to all participants |
| `typing` | `{ conversation_id, user_id, typing: true\|false }` | Ephemeral; not persisted |
| `connected` | `{ user_id, conversations: [uuid] }` | Sent on socket open |
| `auth.expired` | `{}` | Server closes socket after sending |

#### Events — Client → Server

| Event | Payload | Action |
|---|---|---|
| `message.read` | `{ message_id }` | Server marks read, broadcasts to conversation |
| `typing` | `{ conversation_id, typing: bool }` | Server fans out to other participants |

---

### 13.3 `/ws/v1/delivery/{order_id}`

**Auth:** any role party to the order (customer, seller, driver) or admin.

The server applies per-subscriber role filtering before emitting events.

#### Events — Server → Client

| Event | Sent to | Payload | Notes |
|---|---|---|---|
| `delivery.status` | all subscribers | `{ order_id, status, updated_at }` | State transitions |
| `delivery.eta` | all subscribers | `{ order_id, eta_minutes, updated_at }` | ETA recalculated on each location update |
| `delivery.location` | **driver + seller only** | `{ order_id, lat, lng, accuracy_meters, timestamp }` | **Customer sockets NEVER receive this event — server-side filter enforced in WS gateway** |
| `connected` | connecting socket | `{ order_id, your_role }` | Confirms role-aware subscription |
| `auth.expired` | connecting socket | `{}` | Token expired |

#### Server-Side Location Filter (normative)

When the WS gateway receives a `delivery:{order_id}` pub/sub message with type `location`, it iterates all local sockets subscribed to that order and emits:

- `delivery.location` → only sockets where `socket.role ∈ {driver, seller, admin}`
- `delivery.eta` → all sockets (including `customer`)

This filter is enforced in `app/ws/delivery_gateway.py` and must not be modified without a Security Engineer review.

---

## 14. Auth + RBAC Matrix

`✓` = allowed, `—` = forbidden (returns 403)

| Endpoint Group | admin | seller | customer | driver |
|---|---|---|---|---|
| auth signup / login / refresh / me / logout | ✓ | ✓ | ✓ | ✓ |
| invites: create (any role target) | ✓ | — | — | — |
| invites: create (customer/seller target) | ✓ | ✓ | — | — |
| invites: validate (public) | ✓ | ✓ | ✓ | ✓ |
| invites: list own | ✓ | ✓ | — | — |
| invites: revoke own | ✓ | ✓ | — | — |
| users: get/update own profile | ✓ | ✓ | ✓ | ✓ |
| users: get/update any profile | ✓ | — | — | — |
| sellers: create | ✓ | — | — | — |
| stores: create | ✓ | ✓ (own) | — | — |
| stores: get (own) | ✓ | ✓ | — | — |
| stores: get (referral-scoped) | ✓ | — | ✓ | — |
| stores: update | ✓ | ✓ (own) | — | — |
| stores: list all | ✓ | — | — | — |
| sellers: public page | ✓ | — | ✓ (referral-scoped) | — |
| products: CRUD | ✓ | ✓ (own store) | — | — |
| products: list/get | ✓ | ✓ (own) | ✓ (referral-scoped) | — |
| products: image upload URL | ✓ | ✓ (own) | — | — |
| orders: create | — | — | ✓ | — |
| orders: list/get | ✓ | ✓ (own store) | ✓ (own) | ✓ (assigned) |
| orders: cancel | ✓ | — | ✓ (pending only) | — |
| orders: accept / preparing | — | ✓ (own store) | — | — |
| orders: start_delivery / request_driver | — | ✓ (own store) | — | — |
| orders: assign_driver | ✓ | — | — | — |
| deliveries: get (status/ETA only) | — | — | ✓ | — |
| deliveries: get (full, incl. location) | ✓ | ✓ (own) | — | ✓ (assigned) |
| deliveries: post location | — | ✓ (self-deliver) | — | ✓ (assigned) |
| deliveries: complete | ✓ | ✓ (self-deliver) | — | ✓ (assigned) |
| deliveries: metrics | ✓ | ✓ (own) | — | — |
| messages / conversations | ✓ | ✓ | ✓ | ✓ |
| keys: register / fetch | ✓ | ✓ | ✓ | ✓ |
| reviews: create | — | — | ✓ (own order) | — |
| reviews: list | ✓ | ✓ (own store) | — | — |
| admin: users mgmt | ✓ | — | — | — |
| admin: referral graph | ✓ | — | — | — |
| admin: platform settings | ✓ | — | — | — |
| analytics: seller summary (own) | ✓ | ✓ | — | — |
| analytics: any seller summary | ✓ | — | — | — |
| WS messaging | ✓ | ✓ | ✓ | ✓ |
| WS delivery (all events) | ✓ | ✓ | — | ✓ |
| WS delivery (status/ETA only) | — | — | ✓ | — |

---

## 15. Error Codes Table

| Code | HTTP Status | Description |
|---|---|---|
| `INVALID_CREDENTIALS` | 401 | Email/password mismatch |
| `TOKEN_INVALID` | 401 | JWT or refresh token malformed or revoked |
| `TOKEN_EXPIRED` | 401 | JWT or refresh token past expiry |
| `FORBIDDEN` | 403 | Authenticated but role insufficient |
| `NOT_FOUND` | 404 | Resource does not exist or is visibility-hidden |
| `EMAIL_TAKEN` | 409 | Email already registered |
| `STORE_ALREADY_EXISTS` | 409 | Seller already has a store |
| `REVIEW_ALREADY_EXISTS` | 409 | Order already has a review |
| `INVITE_NOT_FOUND` | 404 | Token does not match any invite |
| `INVITE_EXPIRED` | 400 | Invite token past expiry |
| `INVITE_ALREADY_USED` | 409 | Invite token already consumed |
| `STORE_NOT_IN_REFERRAL_CHAIN` | 403 | Customer not referred by this seller |
| `INSUFFICIENT_STOCK` | 400 | Product stock too low for requested quantity |
| `ORDER_NOT_CANCELLABLE` | 400 | Order state does not allow cancellation |
| `ORDER_NOT_DELIVERED` | 400 | Review requires delivered order |
| `PRODUCT_NOT_FOUND` | 404 | Product not found or deleted |
| `KEY_NOT_REGISTERED` | 404 | User has not registered an X25519 public key |
| `SELF_CONVERSATION` | 400 | Cannot create conversation with self |
| `RATE_LIMITED` | 429 | Too many requests — retry after `Retry-After` header |
| `VALIDATION_ERROR` | 422 | Request body failed Pydantic validation |
| `INTERNAL_ERROR` | 500 | Unexpected server error |

---

## 16. Breaking-Change Rules

1. **OpenAPI is authoritative.** Once the FastAPI backend is running, the generated `/openapi.json` is the source of truth for field names, types, and required/optional status. This document summarizes intent; it does not override the generated spec.

2. **Breaking changes require a version bump.** Any of the following is breaking and requires introducing `/api/v2/` for affected endpoints:
   - Removing an endpoint or HTTP method.
   - Removing or renaming a required request/response field.
   - Changing a field type.
   - Changing a 2xx status to a 4xx/5xx for a valid prior input.
   - Changing WebSocket event names or required payload fields.

3. **Additive changes are non-breaking.** Adding optional request fields, adding response fields, adding new endpoints, or adding new optional query params does not require a version bump.

4. **Deprecation policy.** Deprecated endpoints must remain functional for at least one full phase (≥ one sprint) after announcement. Deprecation is signaled via `Deprecation: true` and `Sunset: <date>` response headers.

5. **ADR required.** Any breaking change must be recorded as an ADR in `/docs/adr/` before implementation.

---

## 17. Open Questions for Orchestrator Review

1. **Q-C1 — Driver invitation scope (D-invites):** PROJECT.md states sellers can invite customers or sellers. It is ambiguous whether sellers can invite drivers. Currently the RBAC matrix restricts sellers to `customer|seller` targets. If sellers need to recruit drivers, update the invites create rule. **Proposed resolution:** sellers cannot invite drivers; admin-only.

2. **Q-C2 — Conversation creation initiator:** Who can start a conversation — can a seller initiate a message to a customer, or only vice versa? The current schema permits either party. If there are abuse concerns, the Product Manager should specify directionality restrictions. **Proposed resolution:** bidirectional for now; flag for PM.

3. **Q-C3 — Order listing for drivers:** Drivers can only see orders assigned to them. But during the assignment workflow (after `request_driver`, before `assign_driver`), can a driver see a pool of "available" orders to self-assign? PROJECT.md implies admin always assigns. **Proposed resolution:** admin-only assignment; drivers see only their assigned orders.

4. **Q-C4 — Delivery `complete` endpoint authorization:** A seller self-delivering calls `complete`. But if a driver delivered the order, can the seller also call `complete`? **Proposed resolution:** `complete` is callable by the party who created the delivery (driver or seller), not both. Enforce via `deliveries.driver_id = auth_user.id OR deliveries.seller_id = auth_user.id`.

5. **Q-C5 — Analytics currency:** The `order_analytics_snapshots` table captures amounts. If multi-currency support is added later, the `lifetime_revenue` aggregation becomes ambiguous. **Proposed resolution:** enforce single-currency per store in Phase 2 schema; document multi-currency as out of scope for Phase 1–13.
