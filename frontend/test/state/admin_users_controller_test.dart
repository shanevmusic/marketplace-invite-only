import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/features/admin/data/admin_api.dart';
import 'package:marketplace/features/admin/data/admin_dtos.dart';
import 'package:marketplace/features/admin/state/admin_controllers.dart';

class MockAdminApi extends Mock implements AdminApi {}

AdminUserSummary _u(String id, {String status = 'active'}) => AdminUserSummary(
      id: id,
      email: '$id@example.com',
      displayName: 'U-$id',
      role: 'customer',
      status: status,
      isActive: true,
      createdAt: DateTime.utc(2026, 1, 1),
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

  test('build() loads first page', () async {
    when(() => api.listUsers(limit: any(named: 'limit'))).thenAnswer(
      (_) async => AdminPagedUsers(data: [_u('a'), _u('b')], nextCursor: 'c2'),
    );
    final c = build();
    final s = await c.read(adminUsersControllerProvider.future);
    expect(s.users.length, 2);
    expect(s.hasMore, true);
  });

  test('applyFilter refetches with new filter', () async {
    when(() => api.listUsers(limit: any(named: 'limit')))
        .thenAnswer((_) async => AdminPagedUsers(data: [_u('a')], nextCursor: null));
    when(() => api.listUsers(
          q: 'jane',
          status: 'suspended',
          limit: any(named: 'limit'),
        )).thenAnswer((_) async =>
        AdminPagedUsers(data: [_u('s', status: 'suspended')], nextCursor: null));

    final c = build();
    await c.read(adminUsersControllerProvider.future);
    await c
        .read(adminUsersControllerProvider.notifier)
        .applyFilter(const AdminUsersFilter(q: 'jane', status: 'suspended'));
    final s = c.read(adminUsersControllerProvider).value!;
    expect(s.users.single.status, 'suspended');
    expect(s.filter.q, 'jane');
  });

  test('suspend → refreshes list', () async {
    when(() => api.listUsers(limit: any(named: 'limit')))
        .thenAnswer((_) async => AdminPagedUsers(data: [_u('a')], nextCursor: null));
    when(() => api.suspendUser('a', 'spam')).thenAnswer(
      (_) async => _u('a', status: 'suspended'),
    );

    final c = build();
    await c.read(adminUsersControllerProvider.future);
    await c.read(adminUsersControllerProvider.notifier).suspend('a', 'spam');
    verify(() => api.suspendUser('a', 'spam')).called(1);
    // applyFilter calls listUsers again — build + post-suspend reload = 2.
    verify(() => api.listUsers(limit: any(named: 'limit'))).called(greaterThanOrEqualTo(2));
  });
}
