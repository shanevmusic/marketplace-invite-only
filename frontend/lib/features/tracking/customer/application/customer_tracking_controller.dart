// ADR-0014: this controller is customer-facing. It must NEVER accept or
// propagate coordinate fields. The switch on event.type acts as a type
// allow-list — `delivery.location` events are silently dropped. See
// test/invariants/tracking_coord_boundary_test.dart.
import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../realtime/ws_client.dart';
import '../../../realtime/ws_event.dart';
import '../../shared/delivery_status.dart';

class CustomerTrackingState {
  const CustomerTrackingState({
    required this.status,
    this.etaSeconds,
    this.etaUpdatedAt,
    this.lastUpdatedAt,
    this.destinationLabel = '',
    this.dropCount = 0,
  });

  final TrackingDeliveryStatus status;
  final int? etaSeconds;
  final DateTime? etaUpdatedAt;
  final DateTime? lastUpdatedAt;
  final String destinationLabel;

  /// Count of events intentionally dropped (e.g. `delivery.location`). Tests
  /// assert this increments when a forbidden event is fed in.
  final int dropCount;

  CustomerTrackingState copyWith({
    TrackingDeliveryStatus? status,
    int? etaSeconds,
    DateTime? etaUpdatedAt,
    DateTime? lastUpdatedAt,
    String? destinationLabel,
    int? dropCount,
  }) =>
      CustomerTrackingState(
        status: status ?? this.status,
        etaSeconds: etaSeconds ?? this.etaSeconds,
        etaUpdatedAt: etaUpdatedAt ?? this.etaUpdatedAt,
        lastUpdatedAt: lastUpdatedAt ?? this.lastUpdatedAt,
        destinationLabel: destinationLabel ?? this.destinationLabel,
        dropCount: dropCount ?? this.dropCount,
      );
}

class CustomerTrackingController
    extends FamilyNotifier<CustomerTrackingState, String> {
  StreamSubscription<WsEvent>? _sub;

  @override
  CustomerTrackingState build(String orderId) {
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
    return const CustomerTrackingState(
      status: TrackingDeliveryStatus.pending,
    );
  }

  /// Public entry used by tests to inject raw envelopes.
  void applyEvent(WsEvent ev) => _apply(ev);

  void _apply(WsEvent ev) {
    // Type allow-list. ANY other type — including `delivery.location` — is
    // dropped silently. No pass-through to view state.
    switch (ev.type) {
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
          etaUpdatedAt: DateTime.now(),
          lastUpdatedAt: DateTime.now(),
        );
        return;
      default:
        state = state.copyWith(dropCount: state.dropCount + 1);
        return;
    }
  }

  void seed({
    required TrackingDeliveryStatus status,
    int? etaSeconds,
    DateTime? etaUpdatedAt,
    String destinationLabel = '',
  }) {
    state = state.copyWith(
      status: status,
      etaSeconds: etaSeconds,
      etaUpdatedAt: etaUpdatedAt,
      destinationLabel: destinationLabel,
      lastUpdatedAt: DateTime.now(),
    );
  }
}

final customerTrackingControllerProvider = NotifierProvider.family<
    CustomerTrackingController,
    CustomerTrackingState,
    String>(CustomerTrackingController.new);
