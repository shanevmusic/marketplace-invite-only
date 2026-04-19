import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/features/auth/data/auth_dtos.dart';
import 'package:marketplace/features/auth/data/auth_repository.dart';
import 'package:marketplace/features/auth/state/auth_controller.dart';

import '../helpers/mock_auth_api.dart';

class MockAuthRepository extends Mock implements AuthRepository {}

void main() {
  setUpAll(registerFallbackValues);

  late MockAuthRepository repo;

  setUp(() {
    repo = MockAuthRepository();
    // Default: no stored session, no listener side effects.
    when(() => repo.setSessionExpiredListener(any())).thenReturn(null);
    when(() => repo.seedFromStorage()).thenAnswer((_) async => null);
  });

  ProviderContainer makeContainer() => ProviderContainer(
        overrides: [authRepositoryProvider.overrideWithValue(repo)],
      );

  AuthSession sampleSession({String role = 'customer'}) => AuthSession(
        user: AuthUser(
          id: 'u1',
          email: 'a@b.c',
          role: role,
          displayName: 'A',
        ),
        accessToken: 'acc',
        refreshToken: 'ref',
      );

  test('build returns null when storage is empty', () async {
    final c = makeContainer();
    final value = await c.read(authControllerProvider.future);
    expect(value, isNull);
  });

  test('build returns refreshed session when storage has tokens', () async {
    final session = sampleSession();
    when(() => repo.seedFromStorage()).thenAnswer((_) async => session);
    when(() => repo.refresh()).thenAnswer((_) async => session);

    final c = makeContainer();
    final value = await c.read(authControllerProvider.future);
    expect(value, same(session));
    verify(() => repo.refresh()).called(1);
  });

  test('build falls back to cached on network error', () async {
    final session = sampleSession();
    when(() => repo.seedFromStorage()).thenAnswer((_) async => session);
    when(() => repo.refresh()).thenThrow(AuthApiException(
      statusCode: 0,
      code: 'NETWORK',
    ));

    final c = makeContainer();
    final value = await c.read(authControllerProvider.future);
    expect(value, same(session));
  });

  test('build forces unauth on TOKEN_EXPIRED', () async {
    final session = sampleSession();
    when(() => repo.seedFromStorage()).thenAnswer((_) async => session);
    when(() => repo.refresh()).thenThrow(AuthApiException(
      statusCode: 401,
      code: 'TOKEN_EXPIRED',
    ));
    when(() => repo.logout()).thenAnswer((_) async {});

    final c = makeContainer();
    final value = await c.read(authControllerProvider.future);
    expect(value, isNull);
    expect(c.read(sessionExpiredFlagProvider), isTrue);
    verify(() => repo.logout()).called(1);
  });

  test(
      'build falls back to unauth + clears storage when refresh hangs past timeout',
      () async {
    final session = sampleSession();
    when(() => repo.seedFromStorage()).thenAnswer((_) async => session);
    // refresh() never completes — simulates a slow / unreachable backend.
    final never = Completer<AuthSession>();
    when(() => repo.refresh()).thenAnswer((_) => never.future);
    when(() => repo.logout()).thenAnswer((_) async {});

    final c = makeContainer();

    final value = await c
        .read(authControllerProvider.future)
        .timeout(bootRefreshTimeout + const Duration(seconds: 2));

    expect(value, isNull);
    expect(c.read(authControllerProvider).value, isNull);
    expect(c.read(authControllerProvider).hasError, isFalse);
    // logout() is the code path that clears both in-memory session and
    // SecureAuthStorage (see AuthRepository.logout).
    verify(() => repo.logout()).called(1);
  });

  test('build falls back to unauth when seedFromStorage hangs past timeout',
      () async {
    // seedFromStorage() never completes — simulates flutter_secure_storage_web
    // hanging inside a sandboxed iframe (IndexedDB/SubtleCrypto wedge).
    final never = Completer<AuthSession?>();
    when(() => repo.seedFromStorage()).thenAnswer((_) => never.future);

    final c = makeContainer();

    final value = await c
        .read(authControllerProvider.future)
        .timeout(bootRefreshTimeout + const Duration(seconds: 2));

    expect(value, isNull);
    expect(c.read(authControllerProvider).value, isNull);
    expect(c.read(authControllerProvider).hasError, isFalse);
    // No refresh should be attempted, and no logout call either —
    // there's nothing in memory yet and storage may be broken.
    verifyNever(() => repo.refresh());
    verifyNever(() => repo.logout());
  });

  test('login success updates state with new session', () async {
    final session = sampleSession();
    when(() => repo.login(any())).thenAnswer((_) async => session);

    final c = makeContainer();
    await c.read(authControllerProvider.future);
    await c
        .read(authControllerProvider.notifier)
        .login(email: 'a@b.c', password: 'pw');
    expect(c.read(authControllerProvider).value, same(session));
  });

  test('login failure surfaces error in state', () async {
    final err = AuthApiException(
      statusCode: 401,
      code: 'INVALID_CREDENTIALS',
    );
    when(() => repo.login(any())).thenThrow(err);

    final c = makeContainer();
    await c.read(authControllerProvider.future);
    await c
        .read(authControllerProvider.notifier)
        .login(email: 'a@b.c', password: 'pw');
    expect(c.read(authControllerProvider).hasError, isTrue);
    expect(c.read(authControllerProvider).error, same(err));
  });

  test('logout clears state', () async {
    final session = sampleSession();
    when(() => repo.seedFromStorage()).thenAnswer((_) async => session);
    when(() => repo.refresh()).thenAnswer((_) async => session);
    when(() => repo.logout()).thenAnswer((_) async {});

    final c = makeContainer();
    await c.read(authControllerProvider.future);
    await c.read(authControllerProvider.notifier).logout();
    expect(c.read(authControllerProvider).value, isNull);
    verify(() => repo.logout()).called(1);
  });
}
