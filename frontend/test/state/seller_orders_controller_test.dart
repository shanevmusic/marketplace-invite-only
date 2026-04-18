import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/data/api/api_client.dart';
import 'package:marketplace/features/orders/data/order_api.dart';
import 'package:marketplace/features/orders/data/order_dtos.dart';
import 'package:marketplace/features/orders/state/order_controller.dart';

class MockOrderApi extends Mock implements OrderApi {}

OrderResponse _sample(String status) => OrderResponse(
      id: '00000000-0000-0000-0000-000000000001',
      sellerId: 's1',
      customerId: 'c1',
      status: status,
      totalMinor: 1299,
      currencyCode: 'USD',
      items: const [],
      deliveryAddress:
          const DeliveryAddress(line1: '1 A St', city: 'PDX', country: 'US'),
      createdAt: DateTime.utc(2026, 4, 18),
    );

void main() {
  late MockOrderApi api;

  setUp(() {
    api = MockOrderApi();
  });

  ProviderContainer make() {
    final c = ProviderContainer(overrides: [
      orderApiProvider.overrideWithValue(api),
    ]);
    addTearDown(c.dispose);
    return c;
  }

  test('accept transition mutates in place', () async {
    final pending = _sample('pending');
    final accepted = _sample('accepted');
    when(() => api.list(role: 'seller')).thenAnswer(
      (_) async => OrderListResponse(items: [pending]),
    );
    when(() => api.transition(pending.id, 'accept'))
        .thenAnswer((_) async => accepted);

    final c = make();
    await c.read(sellerOrdersControllerProvider.future);
    await c
        .read(sellerOrdersControllerProvider.notifier)
        .transition(pending.id, 'accept');
    final items = c.read(sellerOrdersControllerProvider).value!;
    expect(items.single.status, 'accepted');
  });

  test('ADR-0003: DELIVERY_ALREADY_STARTED still refreshes list', () async {
    final p = _sample('out_for_delivery');
    when(() => api.list(role: 'seller')).thenAnswer(
      (_) async => OrderListResponse(items: [p]),
    );
    when(() => api.transition(p.id, 'out-for-delivery')).thenThrow(
      ApiException(
        statusCode: 409,
        code: 'DELIVERY_ALREADY_STARTED',
      ),
    );
    final c = make();
    await c.read(sellerOrdersControllerProvider.future);
    await expectLater(
      c
          .read(sellerOrdersControllerProvider.notifier)
          .transition(p.id, 'out-for-delivery'),
      throwsA(isA<ApiException>()),
    );
    // Refresh path was taken (list called twice: initial build + swallow).
    verify(() => api.list(role: 'seller')).called(2);
  });
}
