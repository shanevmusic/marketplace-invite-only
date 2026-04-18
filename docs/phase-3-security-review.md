# Phase 3 Security Review

**Date:** 2026-04-18  
**Reviewer:** Security Engineer Agent  
**Scope:** Phase 3 auth + invite implementation  
**Baseline test count:** 43  
**Final test count:** 61  

---

## 1. Scope and Methodology

### Files Audited

| Path | Focus |
|------|-------|
| `app/core/security.py` | Password hashing, JWT create/decode, refresh token generation |
| `app/core/config.py` | Secret defaults, environment validation |
| `app/core/exceptions.py` | Error codes, HTTP status mapping |
| `app/core/rate_limiter.py` | In-memory rate limiting |
| `app/api/deps.py` | Auth dependency chain, disabled-user blocking |
| `app/api/v1/auth.py` | Route declarations, rate limit decorators |
| `app/api/v1/invites.py` | Invite route RBAC, rate limit decorators |
| `app/services/auth_service.py` | Signup, login, refresh, logout, session management |
| `app/services/invite_service.py` | Invite creation, validation, consumption, revocation |
| `app/schemas/auth.py` | Password min/max length, field validation |
| `app/scripts/seed_dev.py` | Dev seed token predictability |
| `app/main.py` | CORS configuration, exception handlers |
| `app/models/user.py` | is_active, disabled_at, deleted_at fields |
| `docs/adr/0006-server-side-refresh-tokens.md` | RT rotation design |
| `docs/api-contract.md` | Error codes, RBAC matrix |
| `docs/phase-1-reconciliation.md` | Orchestrator rulings |

### Methodology

- Full read of every file listed above.
- Manual trace of each auth flow (signup → login → refresh → logout).
- Verified error paths for user enumeration, token reuse, and disabled accounts.
- Grepped all logger calls for accidental token/password exposure.
- Reviewed JWT creation and decoding for algorithm pinning.
- Reviewed CORS, rate limiter, and SQL query patterns.
- Ran `APP_ENVIRONMENT=test pytest -q` before and after each fix.

---

## 2. Issues Found and Fixed

### Issue 1 — CRITICAL: Predictable hardcoded invite token in seed_dev.py

| | |
|---|---|
| **Severity** | CRITICAL |
| **File** | `app/scripts/seed_dev.py` |
| **Description** | The seller_referral token was hardcoded as `SEEDTOKEN00001234567890ABCDEF01`. If this script were ever run against a staging or production database (or a demo snapshot), the token would be known to anyone with access to the source code. An attacker could bypass the invite-only signup flow. |
| **Fix** | Token is now generated via `secrets.token_urlsafe(32)` (identical to how `invite_service._token()` works). The generated token is printed once at the end of seed output for developer convenience. |
| **Diff summary** | Added `import secrets`. Replaced hardcoded string with `seller_referral_token = secrets.token_urlsafe(32)`. Added `print(f"Seller referral token: {seller_referral_token}")` to seed summary output. |

### Issue 2 — HIGH: TOCTOU window in auth_service.refresh()

| | |
|---|---|
| **Severity** | HIGH |
| **File** | `app/services/auth_service.py` |
| **Description** | Two concurrent requests with the same valid refresh token could both pass the `revoked_at IS NULL` check before either request wrote its revocation. Both requests would then successfully rotate tokens, allowing an attacker to silently clone a session. |
| **Fix** | Added `.with_for_update()` to the `SELECT RefreshToken WHERE token_hash = ?` query inside `refresh()`. The row lock forces serialisation at the database level: the second concurrent request blocks until the first transaction commits, at which point it either finds the row already revoked (→ token-reuse detection) or finds it gone. |
| **Diff summary** | One line change in `auth_service.refresh()`: `sa.select(RefreshToken).where(...).with_for_update()`. |

### Issue 3 — HIGH: APP_JWT_SECRET insecure default allows startup in production

| | |
|---|---|
| **Severity** | HIGH |
| **File** | `app/core/config.py` |
| **Description** | The default JWT secret `change_me_phase_3` was accepted silently in all environments. A developer deploying to production without setting this env var would silently serve tokens signed with a publicly known secret, breaking all JWT security guarantees. |
| **Fix** | Added a `@model_validator(mode="after")` on `Settings` that: (a) in `prod` environment, raises `RuntimeError` preventing startup if the default is detected; (b) in `dev` or `test`, emits a `WARNING` log but allows startup so local development is unaffected. |
| **Diff summary** | Added `_INSECURE_JWT_DEFAULT` constant. Added `_validate_jwt_secret` model validator. Preserved all Phase 2 fields untouched. |

### Issue 4 — MEDIUM: Password minimum length 8 (below OWASP recommended 12)

| | |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/schemas/auth.py` |
| **Description** | The `SignupRequest.password` field had `min_length=8`, below the OWASP-recommended minimum of 12 characters. This allows weak passwords like `Pass123!` (8 chars) to be accepted. |
| **Fix** | Changed `min_length=8` → `min_length=12`. Max length remains 128. Existing test data was verified: all test helper passwords (`AdminPass123!`, `SellerPass123!`, `Password123!`, etc.) meet the 12-character minimum. |
| **Diff summary** | One-line change in `app/schemas/auth.py`. |

### Issue 5 — MEDIUM: Login error exposes disabled-account existence (user enumeration)

| | |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/services/auth_service.py` |
| **Description** | The original `login()` returned `"Account is disabled."` for disabled users, a different message from `"Invalid email or password."` for wrong credentials. This allowed an attacker to enumerate existing accounts: presenting a known email with any password would reveal whether that account existed and was disabled. |
| **Fix** | Unified the disabled-account path to raise the same `InvalidCredentials()` exception as wrong-password. The disabled check is intentionally placed after password verification so it cannot be used as a side channel for account existence. |
| **Diff summary** | Replaced the `if not user.is_active: raise AuthenticationError(...)` branch with `raise InvalidCredentials()`, with explanatory comment. |

### Issue 6 — MEDIUM: get_current_user did not check disabled_at

| | |
|---|---|
| **Severity** | MEDIUM |
| **File** | `app/api/deps.py` |
| **Description** | `get_current_user` checked `User.is_active` but not `User.disabled_at`. The `User` model has both fields (is_active for admin-toggle, disabled_at for timestamp-tracked suspension). A user with `disabled_at IS NOT NULL` but `is_active=True` could still authenticate with a valid JWT. Similarly, `auth_service.refresh()` only checked `is_active`. |
| **Fix** | Added `or user.disabled_at is not None` to the is_active check in both `get_current_user` (deps.py) and `auth_service.refresh()`. Error messages changed to generic "Authentication required." to avoid leaking disabled-account status. |
| **Diff summary** | Two files changed; one line each. |

---

## 3. Issues Deferred

| ID | Severity | Description | Target Phase | Reason |
|----|----------|-------------|--------------|--------|
| D1 | LOW | In-memory rate limiter does not enforce limits across multiple processes or Kubernetes pods | Phase 12 | Requires Redis; dependency not yet in pyproject.toml |
| D2 | LOW | CORS allows `*` in all environments (hardcoded in `main.py`) | Phase 12 | Frontend origins not yet known; comment in code acknowledges this |
| D3 | LOW | JWT tokens lack `aud` (audience) and `iss` (issuer) claims | Phase 12 | Not required by current api-contract; adds value when external service-to-service auth is introduced |
| D4 | INFO | Invite token lookup in `validate_invite` is not constant-time (plaintext equality on indexed column) | Accepted risk (see §4) | Protected by rate limiting + 256-bit entropy; no fix required |

---

## 4. Accepted Risks

### AR-1: Timing side channel on invite token lookup

**Description:** `validate_invite` and `consume_invite` look up invite tokens via `WHERE token = ?` on an indexed column. This is not constant-time — the database response time could vary based on whether the token exists. An attacker with precise timing measurement could theoretically distinguish valid tokens from invalid ones.

**Mitigating controls:**
1. Tokens are generated with `secrets.token_urlsafe(32)` — 256 bits of entropy. Brute-force requires ~2^256 guesses.
2. The `/invites/validate` endpoint is rate-limited to 30 requests/minute per IP (in-memory for Phase 3).
3. Network jitter in realistic deployments dwarfs any sub-millisecond timing difference.

**Decision:** Accept. No fix required. This trade-off is documented per orchestrator guidance.

### AR-2: In-memory rate limiter

**Description:** SlowAPI uses an in-memory store for rate limiting. In a multi-process deployment, rate limit counters are not shared across processes.

**Mitigating controls:**
1. The limiter is disabled in test environments to avoid test interference.
2. For Phase 3 (single-process dev/staging), the in-memory limiter is functional.
3. Phase 12 will replace it with a Redis-backed limiter.

**Decision:** Defer to Phase 12. Documented in rate_limiter.py.

---

## 5. Test Coverage Added

18 new tests added in `tests/test_security.py`. All pass.

| Test | What It Verifies |
|------|------------------|
| `test_login_error_parity_unknown_email` | Unknown email → 401 AUTH_INVALID_CREDENTIALS |
| `test_login_error_parity_wrong_password` | Wrong password → 401 AUTH_INVALID_CREDENTIALS |
| `test_login_error_parity_same_response_body` | Both return identical status + code (enumeration prevention) |
| `test_disabled_user_login_blocked` | is_active=False → 401 on login |
| `test_disabled_user_access_token_rejected` | is_active=False post-issue → 401 on /auth/me |
| `test_disabled_at_user_access_token_rejected` | disabled_at set post-issue → 401 on /auth/me |
| `test_soft_deleted_user_login_blocked` | deleted_at set → 401 on login |
| `test_soft_deleted_user_token_rejected` | deleted_at set post-issue → 401 on /auth/me |
| `test_jwt_alg_none_rejected` | Crafted alg:none JWT → 401 |
| `test_jwt_wrong_secret_rejected` | JWT signed with wrong secret → 401 |
| `test_jwt_unknown_sub_rejected` | Valid JWT, sub=random UUID not in DB → 401 |
| `test_concurrent_refresh_rotation_one_wins` | Sequential simulation: rotated token reuse → 401 |
| `test_default_jwt_secret_hard_fails_in_prod` | Settings(env=prod, secret=default) → raises |
| `test_default_jwt_secret_allowed_in_dev` | Settings(env=dev, secret=default) → no raise |
| `test_default_jwt_secret_allowed_in_test` | Settings(env=test, secret=default) → no raise |
| `test_signup_password_too_short` | 11-char password → 422 VALIDATION_FAILED |
| `test_signup_password_minimum_accepted` | 12-char password → 201 |
| `test_validate_invite_no_pii_leak` | /invites/validate response contains no email/phone/id PII |

---

## 6. Security Checklist

| Control | Status | Notes |
|---------|--------|-------|
| **JWT algorithm pinning** | ✅ PASS | `decode` uses `algorithms=[settings.jwt_algorithm]` (list). `alg:none` rejected. Only HS256 accepted by default. |
| **JWT secret handling** | ✅ PASS (after fix) | Default triggers RuntimeError in prod; warning in dev/test. |
| **JWT claims** | ⚠️ PARTIAL | `sub`, `role`, `jti`, `exp`, `iat` present. `aud` and `iss` not set. Deferred to Phase 12. |
| **Password policy** | ✅ PASS (after fix) | min_length=12, max_length=128. Argon2id with OWASP parameters (time_cost=2, memory=64MiB). |
| **Refresh token rotation** | ✅ PASS (after fix) | SELECT FOR UPDATE prevents TOCTOU. Reuse detection revokes all user sessions. |
| **Disabled-user blocking** | ✅ PASS (after fix) | is_active AND disabled_at checked in get_current_user and refresh service. login returns opaque error. |
| **Soft-delete blocking** | ✅ PASS | deleted_at IS NULL filter on all user lookups. |
| **User enumeration (login)** | ✅ PASS (after fix) | login returns identical 401 + AUTH_INVALID_CREDENTIALS for wrong password, unknown email, and disabled accounts. |
| **User enumeration (signup)** | ✅ PASS | EmailTaken returns generic 409. No timing side channel beyond what's inherent in DB lookup. |
| **CORS** | ⚠️ DEFERRED | `allow_origins=["*"]` hardcoded. Phase 12 will lock down. Documented in main.py. |
| **Token logging** | ✅ PASS | Grepped all logger/log calls. No tokens, passwords, or hashes logged anywhere. |
| **SQL injection** | ✅ PASS | All queries use SQLAlchemy ORM params. text() used only for column defaults and server-side expressions — no user-controlled values. |
| **Invite consumption atomicity** | ✅ PASS | consume_invite uses .with_for_update() and re-checks all constraints inside the transaction. |
| **Invite PII exposure** | ✅ PASS | validate_invite returns only display_name and role (not email, phone, or ID). |
| **Predictable seed tokens** | ✅ PASS (after fix) | Replaced hardcoded token with secrets.token_urlsafe(32). |
| **Rate limiting** | ⚠️ DEFERRED | In-memory only; not cluster-aware. Phase 12 (Redis). Documented. |
| **verify_password constant-time** | ✅ PASS | argon2-cffi uses constant-time comparison internally. Returns False on mismatch — does not short-circuit. |

---

## 7. Sign-off

**Security Engineer approves Phase 3 for merge to main with the following follow-ups scheduled for Phase 12:**

1. **CORS lockdown:** Replace `allow_origins=["*"]` with the explicit frontend origin list once the frontend domain is known. Consider separate origins for dev/staging/prod.

2. **Redis rate limiter:** Replace the in-memory SlowAPI store with a Redis-backed store so that rate limits are enforced across all processes and Kubernetes replicas.

3. **JWT `aud`/`iss` claims:** Add audience and issuer claims to access tokens once service-to-service auth or third-party token validation is required. Ensure `decode_access_token` validates these claims.

4. **Timing side channel on invite lookup:** Remains an accepted risk per §4. If invite token value is ever reduced in entropy (below 128 bits), revisit with HMAC-based constant-time comparison.

No blocking issues remain after the fixes applied in this review.

---

*Review completed by Security Engineer Agent. Test suite: 43 → 61 passing. Zero failures.*
