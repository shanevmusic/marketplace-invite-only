// Phase 10 widget stubbed. ADR-0014 invariant: this widget MUST NOT accept or
// render any driver/seller coordinates. Props are strictly status + eta +
// destination label. Any future change that adds a lat/lng prop here must be
// rejected in code review.
import 'package:flutter/material.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';

enum DeliveryStatus { preparing, outForDelivery, delivered }

class CustomerDeliveryView extends StatelessWidget {
  const CustomerDeliveryView({
    super.key,
    required this.status,
    required this.lastUpdatedAt,
    required this.destinationLabel,
    this.etaSeconds,
  });

  final DeliveryStatus status;
  final int? etaSeconds;
  final DateTime lastUpdatedAt;
  final String destinationLabel;

  String get _statusLabel {
    switch (status) {
      case DeliveryStatus.preparing:
        return 'PREPARING';
      case DeliveryStatus.outForDelivery:
        return 'OUT FOR DELIVERY';
      case DeliveryStatus.delivered:
        return 'DELIVERED';
    }
  }

  String get _etaLabel {
    final s = etaSeconds;
    if (s == null) return 'ETA not available';
    final mins = (s / 60).round();
    return 'Arriving in ~$mins min';
  }

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.s4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.s4,
              vertical: AppSpacing.s2,
            ),
            decoration: BoxDecoration(
              color: context.colors.primaryContainer,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Text(
              _statusLabel,
              style: context.textStyles.labelLarge?.copyWith(
                color: context.colors.onPrimaryContainer,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.s4),
          // Placeholder static map: single destination pin only. Real tile
          // layer wired in Phase 10 via abstract MapProvider.
          AspectRatio(
            aspectRatio: 16 / 10,
            child: Container(
              decoration: BoxDecoration(
                color: context.colors.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(AppRadius.md),
              ),
              alignment: Alignment.center,
              child: Icon(
                Icons.location_on,
                size: 32,
                color: context.colors.primary,
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.s3),
          Text(_etaLabel, style: context.textStyles.titleMedium),
          const SizedBox(height: AppSpacing.s1),
          Text(
            destinationLabel,
            style: context.textStyles.bodyMedium?.copyWith(
              color: context.colors.onSurfaceVariant,
            ),
          ),
        ],
      ),
    );
  }
}
