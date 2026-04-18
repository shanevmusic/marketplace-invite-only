// ADR-0003: transitioning a delivery that has already started is a no-op from
// the client's perspective. The driver controller's markDelivered() surface
// must return `true` even when the server responds with 409
// DELIVERY_ALREADY_STARTED — reflecting idempotent success.
import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:marketplace/data/api/api_client.dart';
import 'package:marketplace/features/orders/data/order_api.dart';
import 'package:marketplace/features/orders/data/order_dtos.dart';
import 'package:marketplace/features/orders/state/order_controller.dart';
import 'package:marketplace/features/realtime/ws_client.dart';
import 'package:marketplace/features/tracking/driver/application/driver_tracking_controller.dart';
import 'package:marketplace/features/tracking/shared/delivery_status.dart';

class _FakeOrderApi extends OrderApi {
  _FakeOrderApi({required this.throwAlreadyStarted}) : super(Dio());
  final bool throwAlreadyStarted;

  @override
  Future<OrderResponse> transition(String orderId, String action) async {
    if (throwAlreadyStarted) {
      throw ApiException(
        statusCode: 409,
        code: 'DELIVERY_ALREADY_STARTED',
        message: 'already',
      );
    }
    return OrderResponse(
      id: orderId,
      sellerId: 's',
      customerId: 'c',
      status: 'delivered',
      totalMinor: 0,
      currencyCode: 'USD',
      items: const [],
      deliveryAddress:
          const DeliveryAddress(line1: '1 Main', city: 'SF', country: 'US'),
      createdAt: DateTime.utc(2026, 1, 1),
    );
  }
}

WsClient _stubWs() => WsClient(
      getToken: () async => null,
      channelFactory: (_) => throw StateError('no real socket'),
    );

void main() {
  test('markDelivered swallows 409 DELIVERY_ALREADY_STARTED', () async {
    final container = ProviderContainer(overrides: [
      orderApiProvider
          .overrideWithValue(_FakeOrderApi(throwAlreadyStarted: true)),
      wsClientProvider.overrideWithValue(_stubWs()),
    ]);
    addTearDown(container.dispose);

    final notifier =
        container.read(driverTrackingControllerProvider('o-1').notifier);
    final ok = await notifier.markDelivered();
    expect(ok, isTrue);
    expect(
      container.read(driverTrackingControllerProvider('o-1')).status,
      TrackingDeliveryStatus.delivered,
    );
  });

  test('markDelivered success path updates status', () async {
    final container = ProviderContainer(overrides: [
      orderApiProvider
          .overrideWithValue(_FakeOrderApi(throwAlreadyStarted: false)),
      wsClientProvider.overrideWithValue(_stubWs()),
    ]);
    addTearDown(container.dispose);

    final notifier =
        container.read(driverTrackingControllerProvider('o-2').notifier);
    final ok = await notifier.markDelivered();
    expect(ok, isTrue);
    expect(
      container.read(driverTrackingControllerProvider('o-2')).status,
      TrackingDeliveryStatus.delivered,
    );
  });
}
