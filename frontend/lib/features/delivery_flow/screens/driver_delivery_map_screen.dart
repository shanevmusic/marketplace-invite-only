import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../state/delivery_flow_providers.dart';

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
  double _driverLat = 40.7589;
  double _driverLng = -73.9851;
  double? _destLat;
  double? _destLng;
  bool _loadingRoute = true;

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
    } catch (_) {
      if (mounted) setState(() => _loadingRoute = false);
    }
  }

  Future<void> _postTick() async {
    // Advance mock driver slightly toward destination each tick.
    if (kIsWeb && _destLat != null && _destLng != null) {
      final dLat = (_destLat! - _driverLat) * 0.15;
      final dLng = (_destLng! - _driverLng) * 0.15;
      _driverLat += dLat;
      _driverLng += dLng;
    }
    try {
      await ref
          .read(deliveryFlowApiProvider)
          .driverLocation(widget.orderId, _driverLat, _driverLng);
    } catch (_) {
      // Swallow — map screen stays usable even if one POST fails.
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
          Container(
            color: Theme.of(context).colorScheme.surfaceContainerHighest,
            child: _loadingRoute
                ? const Center(child: CircularProgressIndicator())
                : _DriverMap(
                    driverLat: _driverLat,
                    driverLng: _driverLng,
                    destLat: _destLat,
                    destLng: _destLng,
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

/// Very lightweight schematic renderer — a real build would use `flutter_map`.
class _DriverMap extends StatelessWidget {
  const _DriverMap({
    required this.driverLat,
    required this.driverLng,
    required this.destLat,
    required this.destLng,
  });
  final double driverLat;
  final double driverLng;
  final double? destLat;
  final double? destLng;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (ctx, box) {
        final center = Offset(box.maxWidth / 2, box.maxHeight / 2);
        const r = 90.0;
        final destAngle = math.pi / 4;
        final destPoint =
            destLat == null ? null : center + Offset(math.cos(destAngle) * r, math.sin(destAngle) * r);
        return CustomPaint(
          size: Size(box.maxWidth, box.maxHeight),
          painter: _Painter(center: center, dest: destPoint),
        );
      },
    );
  }
}

class _Painter extends CustomPainter {
  _Painter({required this.center, required this.dest});
  final Offset center;
  final Offset? dest;

  @override
  void paint(Canvas canvas, Size size) {
    final bg = Paint()..color = const Color(0xFF1A1A1A);
    canvas.drawRect(Offset.zero & size, bg);

    final road = Paint()
      ..color = const Color(0xFF2A2A2A)
      ..strokeWidth = 14;
    for (int i = 0; i < 6; i++) {
      final y = (size.height / 6) * i + 40;
      canvas.drawLine(Offset(0, y), Offset(size.width, y), road);
    }

    if (dest != null) {
      final line = Paint()
        ..color = const Color(0xFFB8722D)
        ..strokeWidth = 3;
      canvas.drawLine(center, dest!, line);

      final destMark = Paint()..color = const Color(0xFFB8722D);
      canvas.drawCircle(dest!, 10, destMark);
    }

    final drv = Paint()..color = Colors.white;
    canvas.drawCircle(center, 9, drv);
    final drvInner = Paint()..color = const Color(0xFFB8722D);
    canvas.drawCircle(center, 5, drvInner);
  }

  @override
  bool shouldRepaint(covariant _Painter oldDelegate) =>
      oldDelegate.dest != dest || oldDelegate.center != center;
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
