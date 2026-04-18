// Route guard: a non-admin deep-linking into /home/admin/* is redirected to
// /error/unknown per frontend-spec/phase-11-admin.md §3.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:marketplace/app/router/app_router.dart';
import 'package:marketplace/app/router/routes.dart';
import 'package:marketplace/features/auth/data/auth_dtos.dart';
import 'package:marketplace/features/auth/data/auth_repository.dart';
import 'package:marketplace/features/auth/state/auth_controller.dart';

class _FakeAuthController extends AuthController {
  _FakeAuthController(this._session);
  final AuthSession? _session;
  @override
  Future<AuthSession?> build() async => _session;
}

AuthSession _session(String role) => AuthSession(
      user: AuthUser(
        id: 'u1',
        email: 'u@example.com',
        role: role,
        displayName: 'U',
      ),
      accessToken: 'a',
      refreshToken: 'r',
    );

Widget _host() {
  return Consumer(builder: (ctx, ref, _) {
    final router = ref.watch(goRouterProvider);
    return MaterialApp.router(routerConfig: router);
  });
}

Future<void> _drain(WidgetTester tester) async {
  for (var i = 0; i < 5; i++) {
    await tester.runAsync(() async {
      await Future<void>.delayed(const Duration(milliseconds: 20));
    });
    for (var j = 0; j < 3; j++) {
      await tester.pump(const Duration(milliseconds: 20));
    }
  }
}

void main() {
  testWidgets('customer deep-linking into /home/admin is redirected to /error/unknown',
      (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider
              .overrideWith(() => _FakeAuthController(_session('customer'))),
        ],
        child: _host(),
      ),
    );
    await _drain(tester);

    final ctx = tester.element(find.byType(MaterialApp).first);
    final container = ProviderScope.containerOf(ctx);
    final router = container.read(goRouterProvider);

    router.go(AppRoutes.adminUsers);
    await _drain(tester);

    expect(
      router.routerDelegate.currentConfiguration.uri.toString(),
      AppRoutes.errorUnknown,
    );
  });

  testWidgets('admin can reach /home/admin/users', (tester) async {
    await tester.pumpWidget(
      ProviderScope(
        overrides: [
          authControllerProvider
              .overrideWith(() => _FakeAuthController(_session('admin'))),
        ],
        child: _host(),
      ),
    );
    await _drain(tester);

    final ctx = tester.element(find.byType(MaterialApp).first);
    final container = ProviderScope.containerOf(ctx);
    final router = container.read(goRouterProvider);

    router.go(AppRoutes.adminUsers);
    await _drain(tester);

    expect(
      router.routerDelegate.currentConfiguration.uri.toString(),
      AppRoutes.adminUsers,
    );
  });
}
