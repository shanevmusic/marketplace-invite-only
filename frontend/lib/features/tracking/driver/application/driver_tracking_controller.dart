// ADR-0014: driver-facing controller. Coordinates ARE allowed here (the whole
// point of driver view is live location). Imports from customer/ are not.
//
// ADR-0003: markDelivered() swallows 409 DELIVERY_ALREADY_STARTED so the
// terminal 'delivered' transition is idempotent.
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../data/api/api_client.dart';
import '../../../orders/state/order_controller.dart';
import '../../../realtime/ws_client.dart';
import '../../../realtime/ws_event.dart';
import '../../_internal_shared/mapbox_delivery_map.dart';
import '../../shared/delivery_status.dart';

class DriverTrackingState {
  const DriverTrackingState({
    required this.status,
    this.driverLocation,
    this.destination,
    this.breadcrumb = const [],
    this.etaSeconds,
    this.lastUpdatedAt,
  });

  final TrackingDeliveryStatus status;
  final MapPoint? driverLocation;
  final MapPoint? destination;
  final List<MapPoint> breadcrumb;
  final int? etaSeconds;
  final DateTime? lastUpdatedAt;

  DriverTrackingState copyWith({
    TrackingDeliveryStatus? status,
    MapPoint? driverLocation,
    MapPoint? destination,
    List<MapPoint>? breadcrumb,
    int? etaSeconds,
    DateTime? lastUpdatedAt,
  }) =>
      DriverTrackingState(
        status: status ?? this.status,
        driverLocation: driverLocation ?? this.driverLocation,
        destination: destination ?? this.destination,
        breadcrumb: breadcrumb ?? this.breadcrumb,
        etaSeconds: etaSeconds ?? this.etaSeconds,
        lastUpdatedAt: lastUpdatedAt ?? this.lastUpdatedAt,
      );
}

class DriverTrackingController
    extends FamilyNotifier<DriverTrackingState, String> {
  StreamSubscription<WsEvent>? _sub;

  @override
  DriverTrackingState build(String orderId) {
    final ws = ref.read(wsClientProvider);
    ws.subscribe(deliveryChannel(orderId));
    _sub = ws.events.listen((ev) {
      if (ev.channel != deliveryChannel(orderId)) return;
      _apply(ev);
    });
    ref.onDispose(() {
      _sub?.cancel();
      ws.unsubscribe(deliveryChannel(orderId));
    });
    return const DriverTrackingState(status: TrackingDeliveryStatus.accepted);
  }

  void applyEvent(WsEvent ev) => _apply(ev);

  void _apply(WsEvent ev) {
    switch (ev.type) {
      case 'delivery.location':
        final lat = (ev.data['lat'] as num?)?.toDouble();
        final lng = (ev.data['lng'] as num?)?.toDouble();
        if (lat == null || lng == null) return;
        final pt = MapPoint(lat: lat, lng: lng);
        state = state.copyWith(
          driverLocation: pt,
          breadcrumb: [...state.breadcrumb, pt].take(200).toList(),
          lastUpdatedAt: DateTime.now(),
        );
        return;
      case 'delivery.status':
        final s = ev.data['status'] as String?;
        if (s == null) return;
        state = state.copyWith(
          status: parseStatus(s),
          lastUpdatedAt: DateTime.now(),
        );
        return;
      case 'delivery.eta':
        final secs = (ev.data['eta_seconds'] as num?)?.toInt();
        state = state.copyWith(
          etaSeconds: secs,
          lastUpdatedAt: DateTime.now(),
        );
        return;
    }
  }

  void seedDestination(MapPoint dest) {
    state = state.copyWith(destination: dest);
  }

  /// Transition order to delivered. ADR-0003: on 409 DELIVERY_ALREADY_STARTED
  /// we treat as success (idempotent terminal state).
  Future<bool> markDelivered() async {
    final api = ref.read(orderApiProvider);
    try {
      final updated = await api.transition(arg, 'deliver');
      state = state.copyWith(
        status: parseStatus(updated.status),
        lastUpdatedAt: DateTime.now(),
      );
      return true;
    } on ApiException catch (e) {
      if (e.isConflict && e.isDeliveryAlreadyStarted) {
        // Already delivered — treat as success.
        state = state.copyWith(
          status: TrackingDeliveryStatus.delivered,
          lastUpdatedAt: DateTime.now(),
        );
        return true;
      }
      rethrow;
    }
  }
}

final driverTrackingControllerProvider = NotifierProvider.family<
    DriverTrackingController,
    DriverTrackingState,
    String>(DriverTrackingController.new);
