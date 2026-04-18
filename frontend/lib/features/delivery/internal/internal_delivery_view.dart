// Phase 10 widget stubbed. Seller/driver/admin-only — never imported in a
// customer/ folder. The 'internal' path segment is the lint guardrail; any
// import path containing both '/customer/' and '/internal/' is rejected by
// frontend/tool/lint/asymmetric_delivery_rule.dart.
import 'package:flutter/material.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';

class LatLng {
  const LatLng(this.lat, this.lng);
  final double lat;
  final double lng;
}

class InternalDeliveryView extends StatelessWidget {
  const InternalDeliveryView({
    super.key,
    required this.orderId,
    required this.customerDropOff,
    required this.breadcrumbs,
    this.driverCurrent,
    this.durationSoFar,
    this.distanceMeters,
    this.onMarkDelivered,
  });

  final String orderId;
  final LatLng customerDropOff;
  final LatLng? driverCurrent;
  final List<LatLng> breadcrumbs;
  final Duration? durationSoFar;
  final int? distanceMeters;
  final VoidCallback? onMarkDelivered;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.s4),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          AspectRatio(
            aspectRatio: 16 / 10,
            child: Container(
              decoration: BoxDecoration(
                color: context.colors.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(AppRadius.md),
              ),
              alignment: Alignment.center,
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Icon(Icons.map, size: 32, color: context.colors.primary),
                  const SizedBox(height: AppSpacing.s2),
                  Text(
                    '${breadcrumbs.length} breadcrumbs',
                    style: context.textStyles.labelMedium,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: AppSpacing.s3),
          Row(
            children: [
              if (durationSoFar != null)
                Expanded(
                  child: Text(
                    'Duration: ${durationSoFar!.inMinutes} min',
                    style: context.textStyles.bodyMedium,
                  ),
                ),
              if (distanceMeters != null)
                Expanded(
                  child: Text(
                    'Distance: ${distanceMeters}m',
                    style: context.textStyles.bodyMedium,
                  ),
                ),
            ],
          ),
        ],
      ),
    );
  }
}
