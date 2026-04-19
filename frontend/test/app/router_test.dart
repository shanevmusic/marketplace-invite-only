// Regression guard: /splash must NEVER be treated as an acceptable settled
// destination. When AuthController resolves to AsyncData(null), the redirect
// should push unauthenticated users from /splash to /login — not leave them
// stranded on the splash screen.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/app/router/app_router.dart';
import 'package:marketplace/app/router/routes.dart';
import 'package:marketplace/features/auth/data/auth_repository.dart';
import 'package:marketplace/features/auth/state/auth_controller.dart';

class _MockAuthRepository extends Mock implements AuthRepository {}

void main() {
  late _MockAuthRepository repo;

  setUp(() {
    repo = _MockAuthRepository();
    when(() => repo.setSessionExpiredListener(any())).thenReturn(null);
    when(() => repo.seedFromStorage()).thenAnswer((_) async => null);
  });

  ProviderContainer makeContainer() => ProviderContainer(
        overrides: [authRepositoryProvider.overrideWithValue(repo)],
      );

  test('redirects splash to /login when session is null and auth settled',
      () async {
    final c = makeContainer();
    // Let AuthController.build() complete with AsyncData(null).
    await c.read(authControllerProvider.future);
    final result = redirectForTest(c, AppRoutes.splash);
    expect(result, AppRoutes.login);
  });

  test('keeps user on splash while auth is still loading', () {
    // Do NOT await authControllerProvider.future — leave it in its initial
    // AsyncLoading state so we exercise the `isLoading` early-return path.
    final c = makeContainer();
    final result = redirectForTest(c, AppRoutes.splash);
    expect(result, isNull);
  });
}
