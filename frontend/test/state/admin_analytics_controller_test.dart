import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/features/admin/data/admin_api.dart';
import 'package:marketplace/features/admin/data/admin_dtos.dart';
import 'package:marketplace/features/admin/state/admin_controllers.dart';

class MockAdminApi extends Mock implements AdminApi {}

const _overview = AdminAnalyticsOverview(
  totalGmvMinor: 123456,
  ordersCount: 7,
  activeUsers24h: 3,
  activeUsers7d: 5,
  activeUsers30d: 9,
  sellerCount: 2,
  customerCount: 10,
  driverCount: 1,
  adminCount: 1,
);

void main() {
  late MockAdminApi api;

  setUp(() {
    api = MockAdminApi();
  });

  ProviderContainer build() {
    final c = ProviderContainer(overrides: [
      adminApiProvider.overrideWithValue(api),
    ]);
    addTearDown(c.dispose);
    return c;
  }

  test('build loads overview + top sellers concurrently', () async {
    when(() => api.overview()).thenAnswer((_) async => _overview);
    when(() => api.topSellers(limit: any(named: 'limit'))).thenAnswer((_) async => const [
          TopSeller(
            sellerId: 's1',
            displayName: 'Acme',
            lifetimeRevenueMinor: 50000,
            lifetimeOrderCount: 3,
          ),
        ]);
    final c = build();
    final s = await c.read(adminAnalyticsControllerProvider.future);
    expect(s.overview.totalGmvMinor, 123456);
    expect(s.topSellers, hasLength(1));
    expect(s.topSellers.first.sellerId, 's1');
  });

  test('refresh re-fetches both endpoints', () async {
    when(() => api.overview()).thenAnswer((_) async => _overview);
    when(() => api.topSellers(limit: any(named: 'limit')))
        .thenAnswer((_) async => const <TopSeller>[]);
    final c = build();
    await c.read(adminAnalyticsControllerProvider.future);
    await c.read(adminAnalyticsControllerProvider.notifier).refresh();
    verify(() => api.overview()).called(2);
    verify(() => api.topSellers(limit: any(named: 'limit'))).called(2);
  });
}
