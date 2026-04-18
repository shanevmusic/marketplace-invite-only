# Frontend Spec — 04 Navigation Map

**Audience:** Frontend Engineer wiring `go_router` under `lib/app/router.dart`.

Routes are defined as `const` paths on an `AppRoutes` class. Every route declares the role(s) that may enter it; the single `redirect` callback is the only place that enforces access. Widgets never re-check role.

---

## 1. Route tree

### 1.1 Unauthenticated / boot

| Path | Screen | Allowed roles | Notes |
|---|---|---|---|
| `/` | Redirector | any | Always redirects — never renders. Resolves session → target. |
| `/splash` | `SplashScreen` | any | Shown while the auth controller is in `AsyncValue.loading`. Brand mark + subtle progress indicator. |
| `/login` | `LoginScreen` | unauth only | Email + password. Link to "I have an invite". |
| `/signup` | `SignupScreen` | unauth only | Requires `invite_token` query param — see §3. |
| `/invite/:token` | `InviteLandingScreen` | any | Validates token. Branches to signup (unauth) or dialog (auth). See §4. |
| `/error/offline` | `OfflineScreen` | any | Shown on boot when the device is offline AND no cached session exists. Retry button. |
| `/error/unknown` | `UnknownErrorScreen` | any | Fallback for uncaught exceptions at the router level. |

### 1.2 Authenticated — role home shells (ShellRoutes)

Shell routes hold the bottom nav and persist tab state. See `03-role-shells.md` for the tab breakdown.

| Shell path | Role | Tabs (paths) |
|---|---|---|
| `/home/customer` | `customer` | `discover`, `orders`, `messages`, `profile` |
| `/home/seller` | `seller` | `dashboard`, `products`, `orders`, `profile` |
| `/home/driver` | `driver` | `available`, `active`, `history`, `profile` |
| `/home/admin` | `admin` | `invites`, `users`, `settings`, `logs` |

Each tab path is the full path, e.g. `/home/customer/discover`. Deep-linking to a specific tab works because each tab is a distinct `GoRoute` nested under the shell.

### 1.3 Authenticated — detail / sub-routes (defined here, bodies are Phase 9–11)

Listed for completeness so route constants can be declared in Phase 8:

| Path | Screen | Allowed roles | Phase |
|---|---|---|---|
| `/home/customer/products/:productId` | Product detail | customer | 9 |
| `/home/customer/orders/:orderId` | Order detail | customer | 9 |
| `/home/customer/messages/:conversationId` | Conversation | customer | 10 |
| `/home/customer/orders/:orderId/track` | Customer delivery view | customer | 10 |
| `/home/customer/orders/:orderId/review` | Leave review | customer | 9 |
| `/home/seller/store/new` | Create store wizard | seller | 9 |
| `/home/seller/products/new` | Add product | seller | 9 |
| `/home/seller/products/:productId/edit` | Edit product | seller | 9 |
| `/home/seller/orders/:orderId` | Seller order detail | seller | 9 |
| `/home/seller/orders/:orderId/track` | Internal delivery view | seller | 10 |
| `/home/seller/messages/:conversationId` | Conversation | seller | 10 |
| `/home/driver/active/:orderId` | Driver delivery screen (InternalDeliveryView) | driver | 10 |
| `/home/admin/invites/new` | Issue invite | admin | 11 |
| `/home/admin/users/:userId` | User detail | admin | 11 |
| `/home/admin/referral-graph` | Referral graph | admin | 11 |

---

## 2. Deep-link behavior

### 2.1 Schemes

Two deep-link entry points, both hitting the same handler:

| Scheme | Example | Routed to |
|---|---|---|
| Custom scheme | `marketplace://invite/abc123` | `/invite/abc123` |
| Universal / App Link (HTTPS) | `https://<domain>/invite/abc123` | `/invite/abc123` |

**Configuration notes (for Frontend Engineer):**
- iOS: `ios/Runner/Info.plist` — `CFBundleURLTypes` with `marketplace` scheme; Associated Domains entitlement with `applinks:<domain>` (domain value TBD by DevOps Phase 13).
- Android: `android/app/src/main/AndroidManifest.xml` — intent-filters for `scheme=marketplace` and `scheme=https host=<domain> pathPrefix=/invite/`.
- Both platforms route into Flutter via the `go_router` deep-link integration.

### 2.2 Seller referral links

Per PRD §3.2, the legacy form `/ref/{seller_id}/{token}` exists in product literature. **We normalize at the server level:** the seller-shareable URL the app generates is `https://<domain>/invite/<token>` where `<token>` is the seller's referral token (multi-use per ADR-0002). The `seller_id` is encoded in the token — the app never parses it out of the URL. This keeps one route pattern for all invite types.

### 2.3 Unknown / malformed deep links

`/invite/<anything>` always lands on `InviteLandingScreen`, which then hits `GET /api/v1/invites/validate?token=...`. Validation errors are handled per `05-auth-flows.md` §4.

---

## 3. Redirect rules (single source of truth)

The `GoRouter.redirect` callback runs on every navigation. Pseudocode:

```dart
String? redirect(BuildContext ctx, GoRouterState state) {
  final authState = ref.read(authControllerProvider);

  // Boot phase: keep on /splash until auth loads.
  if (authState.isLoading) {
    return state.matchedLocation == '/splash' ? null : '/splash';
  }

  // Error on boot (and no cached session): send to /error/offline or /login.
  if (authState.hasError && authState.value == null) {
    if (state.matchedLocation.startsWith('/error/')) return null;
    return _isOfflineError(authState.error) ? '/error/offline' : '/login';
  }

  final session = authState.value; // may be null = unauth
  final loc = state.matchedLocation;
  final onPublic = loc == '/login'
      || loc == '/signup'
      || loc.startsWith('/invite/')
      || loc == '/splash'
      || loc.startsWith('/error/');

  // Unauthenticated users: only public routes allowed.
  if (session == null) {
    return onPublic ? null : '/login';
  }

  // Authenticated: if they hit /login or /signup by accident, bounce home.
  // Exception: /invite/:token when authed — see §4 for the "switch account" dialog.
  if (loc == '/login' || loc == '/signup' || loc == '/splash' || loc == '/') {
    return _homeFor(session.user.role);
  }

  // Role-guarded sections: ensure role matches the shell.
  if (loc.startsWith('/home/customer') && session.user.role != 'customer') {
    return _homeFor(session.user.role);
  }
  if (loc.startsWith('/home/seller') && session.user.role != 'seller') {
    return _homeFor(session.user.role);
  }
  if (loc.startsWith('/home/driver') && session.user.role != 'driver') {
    return _homeFor(session.user.role);
  }
  if (loc.startsWith('/home/admin') && session.user.role != 'admin') {
    return _homeFor(session.user.role);
  }

  return null; // allow
}

String _homeFor(String role) => '/home/$role/${_defaultTab(role)}';
```

**`refreshListenable`:** the router listens to an `AuthRefreshNotifier` that fires whenever `authControllerProvider` state transitions. This re-runs the redirect on login, logout, and token refresh failure.

---

## 4. Invite-link flow (routing layer only — full UX in `05-auth-flows.md` §1, §5)

State when an invite link is opened:

| Cold-start cache state | User tapped `/invite/:token` → |
|---|---|
| No session cached | Navigate to `/invite/:token` → `InviteLandingScreen`: validate token → on success, navigate to `/signup?invite_token=<token>` with `role_choice` surface if seller_referral. On error, show error screen with "Get a new invite" guidance. |
| Valid session cached | Navigate to `/invite/:token` → `InviteLandingScreen` validates token → then shows an `AppDialog`: *"You're signed in as `<email>` (`<role>`). This invite is for a new account. Sign out and use it?"* with actions: *"Use this invite"* (logout → `/signup?invite_token=...`) and *"Stay signed in"* (pop to current home). |
| Expired-refresh session | Treat as unauth (refresh already discarded the session). |

**Why the dialog, not a forced logout:** losing the current logged-in state silently when a user taps a link would be surprising and destructive. Explicit confirmation preserves user agency.

---

## 5. Session / refresh routing

`authControllerProvider` owns all session transitions:

| Trigger | State transition | Router response |
|---|---|---|
| App cold start | `loading` → `data(session?)` or `error` | Splash until resolved, then redirect |
| Successful login | `data(null)` → `data(session)` | Redirect to `_homeFor(role)` |
| Successful signup | `data(null)` → `data(session)` | Redirect to `_homeFor(role)` |
| Access token expiry | Transparent refresh attempt (api client interceptor) | No route change if refresh succeeds |
| Refresh token expiry / invalid | `data(session)` → `data(null)` with a one-shot "Your session expired" toast queued | Redirect to `/login`; toast shows on arrival |
| Explicit logout | `data(session)` → `data(null)` | Redirect to `/login` |
| `/auth/me` returns 401 three times in a row | Treat as refresh failure | Same as above |
| Server returns `USER_DISABLED` | Force logout + show dialog *"Your account has been disabled. Contact admin."* | Redirect to `/login` after dialog ack |

**Transparent refresh contract:** the API client retries a single 401 after a token refresh attempt. Only when the refresh itself fails (or N=3 consecutive 401s after refresh) does the UI surface the expiration.

---

## 6. Guarded routes — summary table

| Path pattern | Must be | Enforced by |
|---|---|---|
| `/` | — | redirect resolves to target |
| `/splash` | — | allowed any state |
| `/login`, `/signup` | unauth (else bounced home) | redirect |
| `/invite/:token` | any (dialog if authed) | screen logic + redirect |
| `/home/customer/**` | role == customer | redirect |
| `/home/seller/**` | role == seller | redirect |
| `/home/driver/**` | role == driver | redirect |
| `/home/admin/**` | role == admin | redirect |
| `/error/**` | any | redirect (allowed always) |

---

## 7. Path constants

Define all paths in `lib/app/routes.dart` as `const` strings and small helper builders for parameterized routes:

```dart
abstract class AppRoutes {
  static const splash = '/splash';
  static const login = '/login';
  static const signup = '/signup';
  static String invite(String token) => '/invite/$token';
  static const customerHome = '/home/customer/discover';
  static const sellerHome = '/home/seller/dashboard';
  static const driverHome = '/home/driver/available';
  static const adminHome = '/home/admin/invites';
  static String orderDetail(String role, String orderId) =>
      '/home/$role/orders/$orderId';
  // ...
}
```

No screen, widget, or test uses a raw path string outside this file.
