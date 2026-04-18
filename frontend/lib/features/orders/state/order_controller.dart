import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
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

/// Polled customer order detail — 30s cadence, cancels on dispose.
class CustomerOrderDetailController
    extends FamilyAsyncNotifier<OrderResponse, String> {
  Timer? _timer;

  @override
  Future<OrderResponse> build(String orderId) async {
    ref.onDispose(() {
      _timer?.cancel();
      _timer = null;
    });
    _scheduleNext();
    return ref.read(orderApiProvider).get(orderId);
  }

  void _scheduleNext() {
    _timer?.cancel();
    _timer = Timer(const Duration(seconds: 30), _poll);
  }

  Future<void> _poll() async {
    try {
      final next = await ref.read(orderApiProvider).get(arg);
      state = AsyncValue.data(next);
    } catch (_) {
      // keep last-known state
    }
    _scheduleNext();
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
