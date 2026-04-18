// ADR-0014: seller-facing controller. Coordinates are allowed here because
// sellers see the same delivery map as the driver (read-only). Imports from
// customer/ are not allowed.
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../realtime/ws_client.dart';
import '../../../realtime/ws_event.dart';
import '../../_internal_shared/mapbox_delivery_map.dart';
import '../../shared/delivery_status.dart';

class SellerTrackingState {
  const SellerTrackingState({
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

  SellerTrackingState copyWith({
    TrackingDeliveryStatus? status,
    MapPoint? driverLocation,
    MapPoint? destination,
    List<MapPoint>? breadcrumb,
    int? etaSeconds,
    DateTime? lastUpdatedAt,
  }) =>
      SellerTrackingState(
        status: status ?? this.status,
        driverLocation: driverLocation ?? this.driverLocation,
        destination: destination ?? this.destination,
        breadcrumb: breadcrumb ?? this.breadcrumb,
        etaSeconds: etaSeconds ?? this.etaSeconds,
        lastUpdatedAt: lastUpdatedAt ?? this.lastUpdatedAt,
      );
}

class SellerTrackingController
    extends FamilyNotifier<SellerTrackingState, String> {
  StreamSubscription<WsEvent>? _sub;

  @override
  SellerTrackingState build(String orderId) {
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
    return const SellerTrackingState(status: TrackingDeliveryStatus.accepted);
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
}

final sellerTrackingControllerProvider = NotifierProvider.family<
    SellerTrackingController,
    SellerTrackingState,
    String>(SellerTrackingController.new);
