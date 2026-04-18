// ADR-0014: The split tracking widget tree enforces a hard boundary between
// the customer view (coord-free) and the driver/seller views (map-based).
// These tests fail the build if any of three invariants is violated:
//
//  1. No file under lib/features/tracking/customer/** mentions lat/lng/
//     latitude/longitude/mapbox at the source-token level.
//  2. No file under lib/features/tracking/customer/** imports from
//     tracking/driver/, tracking/seller/, tracking/_internal_shared/, or
//     package:mapbox_maps_flutter.
//  3. The customer controller drops coordinate-bearing events silently
//     (bumping dropCount) rather than propagating them to the view.
import 'dart:io';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:marketplace/features/realtime/ws_client.dart';
import 'package:marketplace/features/realtime/ws_event.dart';
import 'package:marketplace/features/tracking/customer/application/customer_tracking_controller.dart';
import 'package:marketplace/features/tracking/shared/delivery_status.dart';

/// A no-op WsClient for tests — we drive events via `applyEvent` directly.
/// Uses a channel factory that throws so `.connect()` immediately goes to
/// reconnecting without opening a socket, which is fine since our tests
/// bypass the stream entirely.
WsClient _stubWsClient() => WsClient(
      getToken: () async => null,
      channelFactory: (_) => throw StateError('test stub; no real socket'),
    );

void main() {
  group('ADR-0014 tracking coord boundary', () {
    test('customer/** source has no coordinate tokens', () {
      final dir = Directory('lib/features/tracking/customer');
      expect(dir.existsSync(), isTrue);
      final forbidden = [
        RegExp(r'\blat\b'),
        RegExp(r'\blng\b'),
        RegExp(r'\blatitude\b'),
        RegExp(r'\blongitude\b'),
        RegExp(r'\bmapbox\b', caseSensitive: false),
      ];
      final violations = <String>[];
      for (final f in dir
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'))) {
        final src = f.readAsStringSync();
        final cleaned = src
            .split('\n')
            .where((l) => !l.trimLeft().startsWith('//'))
            .join('\n');
        for (final r in forbidden) {
          if (r.hasMatch(cleaned)) {
            violations.add('${f.path} matches ${r.pattern}');
          }
        }
      }
      expect(violations, isEmpty,
          reason: 'customer tracking must stay coord-free:\n'
              '${violations.join('\n')}');
    });

    test(
        'customer/** does not import driver/, seller/, _internal_shared/, mapbox',
        () {
      final dir = Directory('lib/features/tracking/customer');
      final forbiddenImport = [
        RegExp(r'''/tracking/driver/'''),
        RegExp(r'''/tracking/seller/'''),
        RegExp(r'''/tracking/_internal_shared/'''),
        RegExp(r'''package:mapbox'''),
      ];
      final importRe =
          RegExp(r'''^\s*import\s+['"]([^'"]+)['"]''', multiLine: true);
      final violations = <String>[];
      for (final f in dir
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'))) {
        final src = f.readAsStringSync();
        for (final m in importRe.allMatches(src)) {
          final imp = m.group(1)!;
          for (final r in forbiddenImport) {
            if (r.hasMatch(imp)) {
              violations.add('${f.path} imports $imp');
            }
          }
        }
      }
      expect(violations, isEmpty,
          reason: 'customer/** violated import boundary:\n'
              '${violations.join('\n')}');
    });

    test('customer controller drops delivery.location silently', () {
      final container = ProviderContainer(overrides: [
        wsClientProvider.overrideWithValue(_stubWsClient()),
      ]);
      addTearDown(container.dispose);
      final notifier = container
          .read(customerTrackingControllerProvider('order-1').notifier);
      notifier.applyEvent(const WsEvent(
        channel: 'delivery:order-1',
        type: 'delivery.location',
        data: {'lat': 37.77, 'lng': -122.41},
      ));
      final s = container.read(customerTrackingControllerProvider('order-1'));
      expect(s.dropCount, 1);
      expect(s.status, TrackingDeliveryStatus.pending);
      expect(s.etaSeconds, isNull);
    });

    test('customer controller consumes delivery.status and .eta', () {
      final container = ProviderContainer(overrides: [
        wsClientProvider.overrideWithValue(_stubWsClient()),
      ]);
      addTearDown(container.dispose);
      final notifier = container
          .read(customerTrackingControllerProvider('order-2').notifier);
      notifier
        ..applyEvent(const WsEvent(
          channel: 'delivery:order-2',
          type: 'delivery.status',
          data: {'status': 'out_for_delivery'},
        ))
        ..applyEvent(const WsEvent(
          channel: 'delivery:order-2',
          type: 'delivery.eta',
          data: {'eta_seconds': 600},
        ));
      final s = container.read(customerTrackingControllerProvider('order-2'));
      expect(s.status, TrackingDeliveryStatus.outForDelivery);
      expect(s.etaSeconds, 600);
      expect(s.dropCount, 0);
    });
  });
}
