# Marketplace — Flutter client (Phase 8)

Flutter 3.22+ / Dart 3.4+. Single codebase for iOS, Android, web (dev only).

## Quick start

```bash
cd frontend
flutter pub get
flutter run --dart-define=API_BASE_URL=http://127.0.0.1:8000/api/v1
```

Environment variables (all `--dart-define`):

| Key                | Default                                | Notes                          |
| ------------------ | -------------------------------------- | ------------------------------ |
| `API_BASE_URL`     | `http://127.0.0.1:8000/api/v1`         | Backend base URL               |
| `DEEP_LINK_DOMAIN` | `app.example.com`                      | Universal / App Link domain    |

## Layout

```
lib/
  app/
    deep_links/     deep link handler (app_links)
    router/         go_router config + route constants
    theme/          tokens, ThemeExtensions, AppTheme builders
  data/
    api/            ApiConfig, Dio base
  features/
    auth/
      data/         AuthApi, DTOs, SecureAuthStorage, TokenInterceptor, AuthRepository
      screens/      splash, login, signup, invite landing, error screens
      state/        AuthController (AsyncNotifier)
    delivery/
      customer/     customer-only delivery view (no lat/lng)  — ADR-0014
      internal/     seller/driver/admin delivery view (full)  — ADR-0014
    shell/          role shells (customer/seller/driver/admin)
  shared/widgets/   design-system components
main.dart
test/
  helpers/          MockAuthApi, TestAuthRepository, InMemoryStorage
  lint/             asymmetric delivery import guard
  state/            AuthController unit tests
  widget/           component + screen tests
  integration/      auth flow smoke test
```

## Design system

- Material 3 `ColorScheme` + `TextTheme` per spec §2.
- Semantic (`success`/`warning`) + role badge colors via `ThemeExtension`.
- Spacing/radius/elevation/motion tokens in `lib/app/theme/tokens.dart`.
- Components consume tokens via `context.colors / textStyles / semanticColors / roleBadgeColors`.

## Auth

`AuthController` (`AsyncNotifier<AuthSession?>`) is the single source of truth:

1. On boot: `seedFromStorage()` → if cached, call `refresh()` to validate tokens.
2. TokenInterceptor runs a single-flight refresh on 401; fires `onSessionExpired` if refresh fails.
3. Expired-session toast surfaces via `sessionExpiredFlagProvider`.

Secure storage uses flutter_secure_storage with keys `auth.access`, `auth.refresh`, `auth.user_json`.

## Routing

`go_router` with a single redirect implementing spec §3 matrix:

- loading  → `/splash`
- network error on boot → `/error/offline`
- unauth + private → `/login`
- authed + public → `/home/<role>`
- role-mismatched shell → `/home/<actualRole>`

## Deep links

Schemes:

- `marketplace://invite/<token>` (custom scheme)
- `https://<DEEP_LINK_DOMAIN>/invite/<token>` (Universal Link / App Link)

Unauth: routes to `/invite/:token` which validates and forwards to signup.
Authed: `AppDialog` confirms before tearing down the session.

## Tests

```bash
flutter test
```

See [`SMOKE-TESTING.md`](SMOKE-TESTING.md) for manual device smoke tests.

## ADRs touching this package

- ADR-0009 / ADR-0013: messaging — ChatBubble takes decrypted plaintext only.
- ADR-0014: asymmetric delivery visibility — `customer/` vs `internal/` barrels enforced by a lint test in `test/lint/`.
- ADR-0015: handwritten typed API client (see `docs/adr/0015-frontend-api-client.md`).
