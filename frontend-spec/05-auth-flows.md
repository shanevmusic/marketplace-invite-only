# Frontend Spec — 05 Auth Flows

**Audience:** Frontend Engineer implementing the Phase 8 auth surface.

Each flow is documented as: trigger → screens → server calls → error cases → success landing. All `POST /api/v1/auth/*` and `GET /api/v1/invites/validate` shapes are taken from `docs/api-contract.md`.

Universal rules:
- Every POST that mutates auth state is idempotent-keyed client-side with a UUID stored in the form's controller lifetime.
- No plaintext password is ever logged, stored (except `flutter_secure_storage` for short-lived ephemeral auto-fill is **not** done — users re-type on each login), or sent to analytics.
- Tokens (`access_token`, `refresh_token`) are persisted in `flutter_secure_storage` under keys `auth.access`, `auth.refresh`, `auth.user_json`. Nowhere else.

---

## Flow 1 — First-time user via invite link

**Goal:** a brand-new user taps an invite link in Messages/SMS/email, lands in the app, signs up, and ends on the correct role home.

**Steps**

1. OS delivers deep link (`marketplace://invite/abc123` or `https://<domain>/invite/abc123`) to Flutter.
2. go_router redirect sees no session → routes to `/invite/abc123` (allowed for unauth users).
3. `InviteLandingScreen` renders immediately with a splash spinner + token preview (`"Invite abc1…"` masked) and fires `GET /api/v1/invites/validate?token=abc123`.
4. **Success path (200 `valid: true`):** screen shows a one-screen summary:
   - Headline: *"You've been invited by `<inviter_name>`"*
   - If response `role` == "seller": subhead *"to join as a seller"* — role will be fixed, `role_choice` hidden on signup.
   - If response `role` == "customer": subhead *"to join as a customer"* — role fixed.
   - If the invite is a **seller_referral** (indicated by server response `role: null` or a `type: "seller_referral"` hint — if absent, the signup screen itself offers the role_choice): subhead *"to connect with their store"*, signup shows `role_choice`.
   - CTA *"Continue"* → `/signup?invite_token=abc123` (with `role_choice_required: true|false` passed via route extras).
5. `SignupScreen` (see Flow 5 for the form itself) → on `POST /api/v1/auth/signup` 201:
   - Persist `access_token`, `refresh_token`, `user` to secure storage.
   - `authControllerProvider` transitions to `AsyncValue.data(session)`.
   - Redirect resolves → lands on `_homeFor(session.user.role)`.
6. First-screen experience is the role shell's first-time empty state (see `03-role-shells.md`).

**Error sub-cases** — see Flow 4.

---

## Flow 2 — Returning user cold start

1. App launches → `authControllerProvider` enters `loading`.
2. Splash screen renders; controller reads `auth.refresh` from secure storage.
3. **If no refresh token:** transition to `data(null)` → redirect to `/login`.
4. **If refresh token present:** `POST /api/v1/auth/refresh` → if 200, persist new tokens, fetch `GET /api/v1/auth/me`, transition to `data(session)` → redirect to `_homeFor(role)`.
5. **If refresh fails with `TOKEN_INVALID` or `TOKEN_EXPIRED`:** clear secure storage, transition to `data(null)` with a one-shot toast flag → redirect to `/login`, toast: *"Your session expired. Please sign in again."*
6. **If refresh fails with network error:** transition to `error(OfflineError)` → redirect to `/error/offline` with a **retry** CTA. If the user had a valid cached `user_json` AND `access_token` that hasn't expired (decoded locally from JWT `exp`), optimistically resolve as `data(session)` but mark `offlineMode: true` — Phase 8 does not need to implement offline mode beyond a best-effort; the retry screen is the default.

**UX detail:** splash minimum dwell time is 300ms to prevent a jarring flash on fast cold starts. If auth resolves faster, hold the splash to the minimum.

---

## Flow 3 — Login failure

**Screen:** `LoginScreen` — email + password + "Sign in" button + "I have an invite" link (→ `/invite/`-prompt if we decide to support manual invite entry; otherwise just shows help text).

**Request:** `POST /api/v1/auth/login` with `{email, password}`.

**Failure cases and UI:**

| Server response | UI |
|---|---|
| `400/401 INVALID_CREDENTIALS` | Inline error below the password field: *"Incorrect email or password."* — **do not** distinguish which is wrong (ADR / security baseline: uniform response). Wait 600–900 ms jittered client-side before re-enabling the button to match server's uniform-timing stance; however, the backend already does uniform response server-side, so this client-side jitter is **optional** — the main UX rule is the uniform message. |
| `429 RATE_LIMITED` | Inline banner above form: *"Too many attempts. Try again in a minute."*; button disabled 30 s with a visible countdown. |
| `422` validation | Field-level errors surfaced via `errorText` on `AppTextField`. |
| Network timeout | Snackbar error: *"Can't reach the server. Check your connection."*; button stays enabled for retry. |
| `USER_DISABLED` (if surfaced) | Modal dialog (`AppDialog`): *"Your account has been disabled. Contact admin."* with single dismiss action. |

**No success-leak via timing:** do not run distinct code paths for "email exists" vs "password wrong" on the client. The UI simply sends the request and renders the one-shot error.

**Password visibility toggle** is allowed and recommended (eye icon in field suffix) — this is a UX win and not a leak.

---

## Flow 4 — Signup with invalid / expired / revoked invite

### 4.1 Pre-signup (on `InviteLandingScreen`)

`GET /api/v1/invites/validate` runs first. Error responses:

| Code | Headline | Subhead | CTA |
|---|---|---|---|
| `INVITE_NOT_FOUND` | "Invite not recognized" | "This link isn't valid. Ask for a new invite." | "Contact who invited you" (opens mailto if email captured) OR simple "Close" |
| `INVITE_EXPIRED` | "Invite expired" | "Invites expire for security. Ask for a fresh link." | Same as above |
| `INVITE_ALREADY_USED` | "Invite already used" | "This invite has already been claimed. If that wasn't you, contact an admin." | "Close" |
| Network error | "Can't verify invite" | "Check your connection and try again." | "Retry" |

UI: full-screen `AppEmptyState` on a neutral background, brand mark top-left, no bottom nav (user is unauth). Logged nowhere with the token value in the clear.

### 4.2 Post-signup (race condition — invite consumed between validate and signup)

Rare but possible: server returns `INVITE_ALREADY_USED` from `POST /auth/signup` after `/validate` said OK. Handle identically to 4.1 — replace the signup form with the same empty-state error. No partial-submit toast.

### 4.3 `EMAIL_TAKEN` on signup

Not an invite problem but surfaces here. Inline error on the email field: *"An account with this email already exists."* with a subtle text link below the form: *"Sign in instead →"* routing to `/login` with the email prefilled.

---

## Flow 5 — Signup form (seller_referral with `role_choice`)

**Screen:** `SignupScreen` at `/signup?invite_token=<token>` (route extras carry `roleChoiceRequired: bool` and `inviterName: String`).

**Form fields (top → bottom), in an `AppFormField` each:**

1. **Display name** (`name` in API) — `AppTextField.text`, 2–80 chars, autofillHints `[name]`.
2. **Email** — `AppTextField.email`, HTML5 email validator client-side, autofillHints `[email]`.
3. **Phone** (optional) — `AppTextField.text` with numeric keyboard, autofillHints `[telephoneNumber]`. Label tagged "(optional)".
4. **Password** — `AppTextField.password`, min 10 chars per API, show strength indicator below helper (green at ≥12, amber at 10–11, red below 10). Toggle eye icon.
5. **Role choice** (only if `roleChoiceRequired == true`, i.e. invite is `seller_referral`):
   ```
   Which kind of account do you want?
   ◉  Customer — browse and order from <inviterName>'s store
   ○  Seller — run your own store, invited by <inviterName>
   ```
   Implemented as a vertically-stacked pair of `AppCard.interactive` with a leading radio. Tapping anywhere in the card selects it. Default selection: **Customer** (most seller_referral invitees are customers; a deliberate tap is required to become a seller).

6. Primary button `AppButton.primary` *"Create account"* — disabled until form is valid.
7. Below: small legal line *"By creating an account you agree to Terms & Privacy"* with two text-button links (route targets TBD Phase 11).

**Validation strategy:** synchronous on blur + on submit; server errors (e.g. `EMAIL_TAKEN`) mapped to field-level `errorText` via the form controller.

**Submit payload → `POST /api/v1/auth/signup`:**
```json
{
  "invite_token": "<token>",
  "name": "...",
  "email": "...",
  "phone": "..." or null,
  "password": "...",
  "role_choice": "customer" | "seller"    // only present when roleChoiceRequired
}
```

**Success:** identical to Flow 1 step 5.

---

## Flow 6 — Signup via admin_invite (role fixed)

Same `SignupScreen` as Flow 5 but with `roleChoiceRequired: false` passed from `InviteLandingScreen`. The role-choice section (step 5 above) is **not rendered**. The submitted payload omits `role_choice`. Server has already stamped the role on the invite; the resulting session's role is whatever the invite encoded (customer / seller / driver).

The only visual affordance indicating the fixed role is the pre-signup `InviteLandingScreen` summary: *"You've been invited to join as a <role>"*. Once on the signup form the role is not editable.

---

## Flow 7 — Logout

**Trigger:** Profile tab → *"Sign out"* button (every role shell has this).

1. Tap *"Sign out"* → confirmation `AppDialog`: *"Sign out of this account?"*, primary *"Sign out"* (destructive variant), secondary *"Cancel"*.
2. On confirm: `POST /api/v1/auth/logout` fire-and-forget (don't block UI on it).
3. Clear `auth.access`, `auth.refresh`, `auth.user_json` from secure storage.
4. Clear in-memory caches scoped to the user (discover feed, messages, orders — Riverpod providers for these use `autoDispose` so they reset on session change, but controllers also call `ref.invalidateSelf()` explicitly to be safe).
5. `authControllerProvider` transitions to `data(null)` → redirect to `/login`.
6. A neutral snackbar on arrival: *"Signed out."*

**Network failure on step 2:** still proceed with local logout (device-side state is the source of truth for presence of the session). The refresh token is already invalidated on the server if step 2 eventually lands; if it doesn't, the token expires naturally in ≤7 days per ADR-0006.

**Secure-storage failure:** if clearing fails (vanishingly rare), block the logout with a dialog *"Couldn't complete sign-out. Try again."* — we never leave the user in a half-state.

---

## Flow 8 — Offline / network failure

**Generic rule:** every screen that performs a network call renders a retryable error state on failure.

**Specific behaviors:**

- **Cold start offline with cached session:** user lands on home shell in "offline mode" — data reads return last-known state (Phase 9 wires offline caches; Phase 8 just shows the shell with empty states and a passive banner *"You're offline"* at the top).
- **Cold start offline with no cached session:** `/error/offline` screen (defined in `04-navigation-map.md` §1.1). Big icon, headline *"You're offline"*, subhead *"Sign in once you're back online."*, CTA *"Retry"* which re-runs the boot sequence.
- **Mid-session network failure:** non-blocking snackbar (`AppSnackbar.error`): *"Connection lost. Retrying…"*. Api client auto-retries with exponential backoff; on recovery, a one-shot success snackbar *"Back online."*
- **Form submit offline:** button stays enabled, tapping it fires the request, timeout surfaces as the form-level error banner with *"Retry"*. Never disable the submit button solely because of offline guess — user might be online when they tap.

---

## Flow 9 — Transparent refresh (invisible to user)

The API client (Dio/http-client singleton under `apiClientProvider`) installs one interceptor:

1. If a response is `401` and the request was not the refresh endpoint itself, enqueue the request, issue `POST /api/v1/auth/refresh` with the stored refresh token.
2. If refresh returns 200: swap the stored tokens, re-issue all enqueued requests with the new access token, deliver their results to the original callers.
3. If refresh returns `TOKEN_INVALID` / `TOKEN_EXPIRED` / `AUTH_TOKEN_REUSED` (ADR-0006): abort the queue, fail all pending requests, fire a `SessionExpired` event on `authControllerProvider` → logout flow (Flow 7 steps 3–6, skipping the confirmation dialog) → `/login` with toast *"Your session expired. Please sign in again."*
4. Concurrency: a single in-flight refresh is shared; a mutex (`Completer<String>`) around the refresh call prevents N requests racing into N refresh calls.
5. **Surfacing:** the user sees **nothing** for a normal refresh. Only after 3 consecutive 401-then-refresh failures (or a hard refresh error) do we surface.

**Diagnostic logging:** `[auth] refresh attempt`, `[auth] refresh success`, `[auth] refresh failed: <code>` — never include tokens, never include the password. In production builds, these go to `debugPrint` only (no remote log sink for auth in Phase 8).

---

## Ledger: what Phase 8 must ship for auth

| Flow | Ships in Phase 8? |
|---|---|
| 1 — First-time via invite link | ✅ Required |
| 2 — Returning cold start | ✅ Required |
| 3 — Login failure | ✅ Required |
| 4 — Invalid/expired/revoked invite | ✅ Required |
| 5 — Signup with role_choice | ✅ Required |
| 6 — Signup without role_choice (admin_invite) | ✅ Required |
| 7 — Logout | ✅ Required |
| 8 — Offline | ✅ Required (boot + mid-session snackbar; full offline cache is Phase 9+) |
| 9 — Transparent refresh | ✅ Required |

Everything behind the shells (discover, orders, messages, admin, etc.) is **placeholder** in Phase 8.
