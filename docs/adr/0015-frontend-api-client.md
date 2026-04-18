# 15. Frontend API client — handwritten typed wrapper (not openapi_generator)

Date: 2026-04-18

## Status

Accepted.

## Context

Phase 8 needs a typed HTTP client for auth, invites, and (stubbed) downstream
endpoints. Three options were on the table:

1. **openapi_generator (build-time codegen)** — generate Dart models + a Dio
   client from `docs/api-contract.md` / OpenAPI spec.
2. **freezed + json_serializable + retrofit** — mixed codegen stack.
3. **Handwritten DTOs + hand-rolled `AuthApi`** wrapping Dio.

We also need the client to: (a) honor the error envelope
`{ "error": { "code", "message", "detail" } }` (spec §3.6), (b) run behind a
single-flight refresh interceptor, (c) be easy to mock in widget tests.

## Decision

Use option 3 for Phase 8. DTOs and the `AuthApi` class are handwritten.

## Rationale

- **No build_runner dependency in Phase 8.** openapi_generator, freezed,
  json_serializable, and retrofit all require `dart run build_runner build`
  as a pre-step. The sandboxed CI environment for this phase does not have
  Flutter SDK network egress guaranteed. Handwritten code always compiles.
- **Contract surface is small.** Phase 8 covers 6 endpoints (`/auth/signup`,
  `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`,
  `/invites/validate`). The marginal cost of writing DTOs by hand is tiny
  compared with adding a codegen toolchain.
- **Error mapping is custom anyway.** Our backend returns a
  `{"error": {...}}` envelope that openapi_generator would not decode into
  our `AuthApiException` shape without post-processing. A hand-written
  `_toException` is straightforward.
- **Mock ergonomics.** `class MockAuthApi extends Mock implements AuthApi` is
  a one-liner with mocktail; codegen'd clients often require additional
  plumbing.
- **Swappable later.** All call sites go through `AuthApi` / `AuthRepository`.
  We can regenerate a codegen'd client behind the same interface in Phase 9+
  without a ripple.

## Consequences

- We must update DTOs by hand when the backend contract changes. Mitigated
  by: (a) keeping DTOs co-located in `lib/features/auth/data/auth_dtos.dart`;
  (b) the DTO file header pins the backend commit it matched.
- No compile-time guarantee that DTO fields match backend schema. Mitigated
  by integration tests that exercise the real endpoints end-to-end.
- When Phase 9 adds product/order/messaging endpoints, we will reassess. If
  the total endpoint count exceeds ~25, switching to codegen becomes
  attractive — revisit then.

## Alternatives considered

- **openapi_generator**: rejected for Phase 8 due to build_runner
  requirement and custom error envelope mismatch.
- **dio + freezed DTOs (no retrofit)**: still requires build_runner for
  freezed/json_serializable; buys us union types we don't need yet.
- **http package**: rejected — we need interceptors for single-flight refresh
  and header management, which Dio provides out of the box. (`package:http`
  is also forbidden by phase constraints.)

## References

- `frontend/lib/features/auth/data/auth_api.dart`
- `frontend/lib/features/auth/data/auth_dtos.dart`
- `frontend/lib/features/auth/data/token_interceptor.dart`
- spec §3.6 (error envelope)
