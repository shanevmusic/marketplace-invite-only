// Regression test for the dark-theme refactor (commit 55edb78) where
// AdminShell was rendering as a blank screen at /home/admin/<tab>. The
// underlying bug: `_adminSubRoutes` (previously `_basicSubRoutes`) returned
// `SizedBox.shrink()` for the `:tab` child route, so go_router matched the
// most-specific child and never built AdminShell for deep-link tab paths.
import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/app/router/app_router.dart';
import 'package:marketplace/app/router/routes.dart';
import 'package:marketplace/app/theme/app_theme.dart';
import 'package:marketplace/data/api/api_client.dart';
import 'package:marketplace/features/admin/data/admin_api.dart';
import 'package:marketplace/features/admin/data/admin_dtos.dart';
import 'package:marketplace/features/admin/state/admin_controllers.dart';
import 'package:marketplace/features/auth/data/auth_dtos.dart';
import 'package:marketplace/features/auth/data/auth_repository.dart';
import 'package:marketplace/features/auth/state/auth_controller.dart';
import 'package:marketplace/features/shell/role_shell.dart';

class _MockAdminApi extends Mock implements AdminApi {}

class _FakeAuthController extends AuthController {
  _FakeAuthController(this._session);
  final AuthSession? _session;
  @override
  Future<AuthSession?> build() async => _session;
}

AuthSession _adminSession() => AuthSession(
      user: AuthUser(
        id: 'u1',
        email: 'admin@example.com',
        role: 'admin',
        displayName: 'Admin',
      ),
      accessToken: 'a',
      refreshToken: 'r',
    );

AdminAnalyticsOverview _overview() => const AdminAnalyticsOverview(
      totalGmvMinor: 0,
      ordersCount: 0,
      activeUsers24h: 0,
      activeUsers7d: 0,
      activeUsers30d: 0,
      sellerCount: 0,
      customerCount: 0,
      driverCount: 0,
      adminCount: 0,
    );

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
  late _MockAdminApi adminApi;

  setUp(() {
    adminApi = _MockAdminApi();
    when(() => adminApi.listUsers(
          q: any(named: 'q'),
          role: any(named: 'role'),
          status: any(named: 'status'),
          cursor: any(named: 'cursor'),
          limit: any(named: 'limit'),
        )).thenAnswer(
        (_) async => const AdminPagedUsers(data: [], nextCursor: null));
    when(() => adminApi.listProducts(
          q: any(named: 'q'),
          status: any(named: 'status'),
          sellerId: any(named: 'sellerId'),
          cursor: any(named: 'cursor'),
          limit: any(named: 'limit'),
        )).thenAnswer(
        (_) async => const AdminPagedProducts(data: [], nextCursor: null));
    when(() => adminApi.overview()).thenAnswer((_) async => _overview());
    when(() => adminApi.topSellers(limit: any(named: 'limit')))
        .thenAnswer((_) async => []);
    when(() => adminApi.getRetention()).thenAnswer((_) async => 30);
    when(() => adminApi.migrationVersion())
        .thenAnswer((_) async => '20260101_001');
  });

  Widget host() {
    return Consumer(builder: (ctx, ref, _) {
      final router = ref.watch(goRouterProvider);
      return MaterialApp.router(
        theme: AppTheme.dark(),
        routerConfig: router,
      );
    });
  }

  Widget app() => ProviderScope(
        overrides: [
          authControllerProvider
              .overrideWith(() => _FakeAuthController(_adminSession())),
          apiClientProvider.overrideWithValue(Dio()),
          adminApiProvider.overrideWithValue(adminApi),
        ],
        child: host(),
      );

  testWidgets('AdminShell renders (not SizedBox.shrink) at /home/admin/users',
      (tester) async {
    await tester.pumpWidget(app());
    await _drain(tester);

    final ctx = tester.element(find.byType(MaterialApp).first);
    final container = ProviderScope.containerOf(ctx);
    final router = container.read(goRouterProvider);
    router.go(AppRoutes.adminUsers);
    await _drain(tester);

    expect(tester.takeException(), isNull);
    expect(find.byType(AdminShell), findsWidgets,
        reason: 'Deep-link to /home/admin/users must build AdminShell, '
            'not the SizedBox.shrink() from the old _basicSubRoutes');

    final scaffolds =
        tester.widgetList<Scaffold>(find.byType(Scaffold)).toList();
    expect(scaffolds, isNotEmpty);

    final theme = Theme.of(tester.element(find.byType(AdminShell).first));
    expect(theme.scaffoldBackgroundColor, isNot(equals(Colors.white)));
    for (final s in scaffolds) {
      final effectiveBg = s.backgroundColor ?? theme.scaffoldBackgroundColor;
      expect(effectiveBg, isNot(equals(Colors.white)),
          reason: 'Every admin Scaffold must resolve to the dark theme bg');
    }

    expect(find.text('Users'), findsWidgets);
    expect(find.text('Issue invite'), findsOneWidget);
  });

  for (final path in [
    AppRoutes.adminUsers,
    AppRoutes.adminContent,
    AppRoutes.adminAnalytics,
    AppRoutes.adminOps,
  ]) {
    testWidgets('AdminShell renders at $path', (tester) async {
      await tester.pumpWidget(app());
      await _drain(tester);

      final ctx = tester.element(find.byType(MaterialApp).first);
      final container = ProviderScope.containerOf(ctx);
      final router = container.read(goRouterProvider);
      router.go(path);
      await _drain(tester);

      expect(tester.takeException(), isNull);
      expect(find.byType(AdminShell), findsWidgets,
          reason: 'AdminShell must render at $path '
              '(not SizedBox.shrink from the pre-fix _basicSubRoutes)');
    });
  }
}
