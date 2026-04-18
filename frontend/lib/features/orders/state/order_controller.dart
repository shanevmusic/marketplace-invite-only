import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import '../../realtime/ws_client.dart';
import '../../realtime/ws_event.dart';
import '../../tracking/shared/delivery_status.dart';
import '../data/order_api.dart';
import '../data/order_dtos.dart';

final orderApiProvider = Provider<OrderApi>((ref) {
  return OrderApi(ref.watch(apiClientProvider));
});

/// Seller-inbox: orders where role=seller.
class SellerOrdersController extends AsyncNotifier<List<OrderResponse>> {
  @override
  Future<List<OrderResponse>> build() async {
    final r = await ref.read(orderApiProvider).list(role: 'seller');
    return r.items;
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final r = await ref.read(orderApiProvider).list(role: 'seller');
      return r.items;
    });
  }

  Future<OrderResponse> transition(String orderId, String action) async {
    final api = ref.read(orderApiProvider);
    try {
      final updated = await api.transition(orderId, action);
      final cur = state.value ?? [];
      state = AsyncValue.data([
        for (final o in cur)
          if (o.id == orderId) updated else o
      ]);
      return updated;
    } on ApiException catch (e) {
      if (e.isConflict && e.isDeliveryAlreadyStarted) {
        // ADR-0003: idempotent — swallow, refresh instead.
        await refresh();
        rethrow;
      }
      rethrow;
    }
  }
}

final sellerOrdersControllerProvider =
    AsyncNotifierProvider<SellerOrdersController, List<OrderResponse>>(
        SellerOrdersController.new);

/// Customer orders list.
class CustomerOrdersController extends AsyncNotifier<List<OrderResponse>> {
  @override
  Future<List<OrderResponse>> build() async {
    final r = await ref.read(orderApiProvider).list(role: 'customer');
    return r.items;
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final r = await ref.read(orderApiProvider).list(role: 'customer');
      return r.items;
    });
  }
}

final customerOrdersControllerProvider =
    AsyncNotifierProvider<CustomerOrdersController, List<OrderResponse>>(
        CustomerOrdersController.new);

/// Single order detail (family).
final orderByIdProvider =
    FutureProvider.family<OrderResponse, String>((ref, id) async {
  return ref.read(orderApiProvider).get(id);
});

/// Customer order detail. Initial fetch then live updates from the
/// `delivery:{orderId}` WS channel. ADR-0014: only status + eta are consumed;
/// coordinate-bearing events are ignored. No 30s polling.
class CustomerOrderDetailController
    extends FamilyAsyncNotifier<OrderResponse, String> {
  StreamSubscription<WsEvent>? _sub;

  @override
  Future<OrderResponse> build(String orderId) async {
    final ws = ref.read(wsClientProvider);
    ws.subscribe(deliveryChannel(orderId));
    _sub = ws.events.listen((ev) {
      if (ev.channel != deliveryChannel(orderId)) return;
      _applyWs(ev);
    });
    ref.onDispose(() {
      _sub?.cancel();
      ws.unsubscribe(deliveryChannel(orderId));
    });
    return ref.read(orderApiProvider).get(orderId);
  }

  void _applyWs(WsEvent ev) {
    final cur = state.value;
    if (cur == null) return;
    switch (ev.type) {
      case 'delivery.status':
        final s = ev.data['status'] as String?;
        if (s == null) return;
        // Parse to validate then write canonical string.
        parseStatus(s);
        state = AsyncValue.data(OrderResponse(
          id: cur.id,
          sellerId: cur.sellerId,
          customerId: cur.customerId,
          status: s,
          totalMinor: cur.totalMinor,
          currencyCode: cur.currencyCode,
          items: cur.items,
          deliveryAddress: cur.deliveryAddress,
          createdAt: cur.createdAt,
          storeName: cur.storeName,
        ));
        return;
      default:
        // Ignore non-status events (incl. delivery.location) on the
        // customer-facing order detail. Tracking view has its own controller
        // with a coord-free type allow-list.
        return;
    }
  }

  Future<void> refreshNow() async {
    final next = await AsyncValue.guard(
      () => ref.read(orderApiProvider).get(arg),
    );
    state = next;
  }
}

final customerOrderDetailProvider = AsyncNotifierProvider.family<
    CustomerOrderDetailController,
    OrderResponse,
    String>(CustomerOrderDetailController.new);
