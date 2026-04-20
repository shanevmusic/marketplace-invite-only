import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:latlong2/latlong.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../state/delivery_flow_providers.dart';

const Color _kBurntAmber = Color(0xFFB8722D);

/// Driver-side map + "complete delivery" flow.
///
/// Web demo mocks GPS (kIsWeb) — native builds would wire geolocator here.
class DriverDeliveryMapScreen extends ConsumerStatefulWidget {
  const DriverDeliveryMapScreen({super.key, required this.orderId});
  final String orderId;

  @override
  ConsumerState<DriverDeliveryMapScreen> createState() => _State();
}

class _State extends ConsumerState<DriverDeliveryMapScreen> {
  Timer? _tick;
  final MapController _mapController = MapController();
  double _driverLat = 40.7589;
  double _driverLng = -73.9851;
  double? _destLat;
  double? _destLng;
  bool _loadingRoute = true;
  bool _didInitialFit = false;

  @override
  void initState() {
    super.initState();
    _loadRoute();
    _tick = Timer.periodic(const Duration(seconds: 10), (_) => _postTick());
  }

  @override
  void dispose() {
    _tick?.cancel();
    super.dispose();
  }

  Future<void> _loadRoute() async {
    final api = ref.read(deliveryFlowApiProvider);
    try {
      final r = await api.driverRoute(widget.orderId);
      final lat = (r['customer_lat'] as num?)?.toDouble();
      final lng = (r['customer_lng'] as num?)?.toDouble();
      if (!mounted) return;
      setState(() {
        _destLat = lat;
        _destLng = lng;
        _loadingRoute = false;
      });
      // Fit bounds once we have both points.
      WidgetsBinding.instance.addPostFrameCallback((_) => _fitBounds());
    } catch (_) {
      if (mounted) setState(() => _loadingRoute = false);
    }
  }

  Future<void> _postTick() async {
    // Advance mock driver slightly toward destination each tick.
    if (kIsWeb && _destLat != null && _destLng != null) {
      final dLat = (_destLat! - _driverLat) * 0.15;
      final dLng = (_destLng! - _driverLng) * 0.15;
      if (mounted) {
        setState(() {
          _driverLat += dLat;
          _driverLng += dLng;
        });
      } else {
        _driverLat += dLat;
        _driverLng += dLng;
      }
      _fitBounds();
    }
    try {
      await ref
          .read(deliveryFlowApiProvider)
          .driverLocation(widget.orderId, _driverLat, _driverLng);
    } catch (_) {
      // Swallow — map screen stays usable even if one POST fails.
    }
  }

  void _fitBounds() {
    if (_destLat == null || _destLng == null) return;
    final driver = LatLng(_driverLat, _driverLng);
    final dest = LatLng(_destLat!, _destLng!);
    final bounds = LatLngBounds.fromPoints([driver, dest]);
    try {
      _mapController.fitCamera(
        CameraFit.bounds(
          bounds: bounds,
          padding: const EdgeInsets.fromLTRB(48, 48, 48, 220),
          maxZoom: 16,
        ),
      );
      _didInitialFit = true;
    } catch (_) {
      // Controller not attached yet — retry on next frame.
      if (!_didInitialFit) {
        WidgetsBinding.instance.addPostFrameCallback((_) => _fitBounds());
      }
    }
  }

  Future<void> _openCompleteSheet() async {
    final ok = await showModalBottomSheet<bool>(
      context: context,
      isScrollControlled: true,
      builder: (ctx) =>
          _CompleteDeliverySheet(orderId: widget.orderId),
    );
    if (ok == true && mounted) {
      context.go(AppRoutes.driverActive);
    }
  }

  @override
  Widget build(BuildContext context) {
    final t = context.textStyles;
    final driver = LatLng(_driverLat, _driverLng);
    final dest = (_destLat != null && _destLng != null)
        ? LatLng(_destLat!, _destLng!)
        : null;
    final initialCenter = dest == null
        ? driver
        : LatLng(
            (driver.latitude + dest.latitude) / 2,
            (driver.longitude + dest.longitude) / 2,
          );

    return Scaffold(
      appBar: AppTopBar(
        title: 'Delivery',
        trailing: [
          IconButton(
            icon: const Icon(Icons.chat_bubble_outline),
            onPressed: () =>
                context.push(AppRoutes.orderChat(widget.orderId)),
          ),
        ],
      ),
      body: Stack(
        children: [
          Positioned.fill(
            child: _loadingRoute
                ? const Center(child: CircularProgressIndicator())
                : FlutterMap(
                    mapController: _mapController,
                    options: MapOptions(
                      initialCenter: initialCenter,
                      initialZoom: 14,
                      interactionOptions: const InteractionOptions(
                        flags: InteractiveFlag.all & ~InteractiveFlag.rotate,
                      ),
                    ),
                    children: [
                      TileLayer(
                        urlTemplate:
                            'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                        userAgentPackageName: 'com.marketplace.app',
                        maxNativeZoom: 19,
                      ),
                      if (dest != null)
                        PolylineLayer(
                          polylines: [
                            Polyline(
                              points: [driver, dest],
                              color: _kBurntAmber,
                              strokeWidth: 4,
                            ),
                          ],
                        ),
                      MarkerLayer(
                        markers: [
                          Marker(
                            point: driver,
                            width: 40,
                            height: 40,
                            child: const _DriverMarker(),
                          ),
                          if (dest != null)
                            Marker(
                              point: dest,
                              width: 40,
                              height: 40,
                              alignment: Alignment.topCenter,
                              child: const Icon(
                                Icons.location_on,
                                color: Colors.redAccent,
                                size: 40,
                                shadows: [
                                  Shadow(
                                    color: Colors.black54,
                                    blurRadius: 4,
                                    offset: Offset(0, 2),
                                  ),
                                ],
                              ),
                            ),
                        ],
                      ),
                      const _OsmAttribution(),
                    ],
                  ),
          ),
          Align(
            alignment: Alignment.bottomCenter,
            child: SafeArea(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.surface,
                    borderRadius: BorderRadius.circular(12),
                    boxShadow: const [
                      BoxShadow(blurRadius: 8, color: Colors.black26),
                    ],
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.stretch,
                    children: [
                      Text('Arrived at the customer?', style: t.titleMedium),
                      const SizedBox(height: 12),
                      AppButton(
                        label: 'Complete delivery',
                        expand: true,
                        onPressed: _openCompleteSheet,
                      ),
                    ],
                  ),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DriverMarker extends StatelessWidget {
  const _DriverMarker();

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: _kBurntAmber,
        shape: BoxShape.circle,
        border: Border.all(color: Colors.white, width: 2),
        boxShadow: const [
          BoxShadow(
            color: Colors.black45,
            blurRadius: 6,
            offset: Offset(0, 2),
          ),
        ],
      ),
      child: const Icon(
        Icons.local_shipping,
        color: Colors.white,
        size: 22,
      ),
    );
  }
}

class _OsmAttribution extends StatelessWidget {
  const _OsmAttribution();

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.bottomRight,
      child: Padding(
        padding: const EdgeInsets.only(right: 4, bottom: 4),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: Colors.black.withValues(alpha: 0.55),
            borderRadius: BorderRadius.circular(4),
          ),
          child: const Text(
            '© OpenStreetMap contributors',
            style: TextStyle(
              color: Colors.white,
              fontSize: 10,
            ),
          ),
        ),
      ),
    );
  }
}

class _CompleteDeliverySheet extends ConsumerStatefulWidget {
  const _CompleteDeliverySheet({required this.orderId});
  final String orderId;

  @override
  ConsumerState<_CompleteDeliverySheet> createState() => _CompleteState();
}

class _CompleteState extends ConsumerState<_CompleteDeliverySheet> {
  final _ctrl = TextEditingController();
  bool _busy = false;
  String? _error;
  int _remaining = 3;
  bool _locked = false;

  Future<void> _submit() async {
    if (_busy) return;
    final code = _ctrl.text.trim();
    if (code.length != 6 || int.tryParse(code) == null) {
      setState(() => _error = 'Enter the 6-digit code');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    try {
      await ref
          .read(deliveryFlowApiProvider)
          .driverComplete(widget.orderId, code);
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } catch (e) {
      final msg = e.toString();
      setState(() {
        _busy = false;
        if (msg.contains('423') || msg.contains('LOCKED')) {
          _locked = true;
          _error = 'Locked after 3 failed attempts. Contact support.';
        } else {
          _remaining = _remaining > 0 ? _remaining - 1 : 0;
          _error = 'Incorrect code. $_remaining attempts remaining.';
        }
      });
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final t = context.textStyles;
    return Padding(
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 24,
        bottom: MediaQuery.of(context).viewInsets.bottom + 24,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Text('Enter the customer code', style: t.titleLarge),
          const SizedBox(height: 8),
          Text('Ask the customer for the 6-digit code shown on their device.',
              style: t.bodyMedium),
          const SizedBox(height: 16),
          TextField(
            controller: _ctrl,
            enabled: !_busy && !_locked,
            keyboardType: TextInputType.number,
            maxLength: 6,
            textAlign: TextAlign.center,
            style: const TextStyle(
                fontSize: 28, letterSpacing: 8, fontWeight: FontWeight.w700),
            decoration: const InputDecoration(
              counterText: '',
              border: OutlineInputBorder(),
            ),
          ),
          if (_error != null) ...[
            const SizedBox(height: 8),
            Text(_error!, style: t.bodyMedium?.copyWith(color: Colors.redAccent)),
          ],
          const SizedBox(height: 16),
          AppButton(
            label: 'Submit',
            expand: true,
            isLoading: _busy,
            onPressed: _locked ? null : _submit,
          ),
        ],
      ),
    );
  }
}
