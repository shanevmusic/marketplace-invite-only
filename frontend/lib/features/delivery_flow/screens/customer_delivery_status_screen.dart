import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../state/delivery_flow_providers.dart';

/// Coordinate-free delivery status — customers never see driver lat/lng.
/// Shows ETA + the 6-digit handoff code.
class CustomerDeliveryStatusScreen extends ConsumerStatefulWidget {
  const CustomerDeliveryStatusScreen({super.key, required this.orderId});
  final String orderId;

  @override
  ConsumerState<CustomerDeliveryStatusScreen> createState() =>
      _State();
}

class _State extends ConsumerState<CustomerDeliveryStatusScreen> {
  Timer? _poll;

  @override
  void initState() {
    super.initState();
    _poll = Timer.periodic(const Duration(seconds: 30), (_) {
      ref.invalidate(customerEtaProvider(widget.orderId));
    });
  }

  @override
  void dispose() {
    _poll?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final etaAsync = ref.watch(customerEtaProvider(widget.orderId));
    final codeAsync = ref.watch(customerCodeProvider(widget.orderId));
    final t = context.textStyles;

    return Scaffold(
      appBar: AppTopBar(title: 'Driver on the way'),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Estimated time of arrival', style: t.bodyMedium),
            const SizedBox(height: 8),
            etaAsync.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, __) => Text('ETA unavailable', style: t.bodyMedium),
              data: (data) {
                final eta = data['eta_seconds'] as int?;
                final label = eta == null
                    ? 'Calculating…'
                    : '${(eta / 60).ceil()} min';
                return Text(label, style: t.headlineLarge);
              },
            ),
            const SizedBox(height: 32),
            Text('Show this code to your driver', style: t.bodyMedium),
            const SizedBox(height: 8),
            codeAsync.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, __) => Text('Code unavailable', style: t.bodyMedium),
              data: (data) {
                final code = (data['code'] as String?) ?? '------';
                return _CodeDisplay(code: code);
              },
            ),
            const Spacer(),
            AppButton(
              label: 'Open chat',
              expand: true,
              onPressed: () =>
                  context.push(AppRoutes.orderChat(widget.orderId)),
            ),
          ],
        ),
      ),
    );
  }
}

class _CodeDisplay extends StatelessWidget {
  const _CodeDisplay({required this.code});
  final String code;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 24),
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Text(
        code,
        style: const TextStyle(
          fontSize: 48,
          letterSpacing: 8,
          fontWeight: FontWeight.w700,
        ),
      ),
    );
  }
}
