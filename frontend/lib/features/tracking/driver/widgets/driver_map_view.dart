import 'package:flutter/material.dart';

import '../../../../app/theme/theme_extensions.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../_internal_shared/mapbox_delivery_map.dart';
import '../../shared/delivery_status.dart';
import '../application/driver_tracking_controller.dart';

class DriverMapView extends StatelessWidget {
  const DriverMapView({
    super.key,
    required this.state,
    required this.orderId,
    required this.onMarkDelivered,
  });

  final DriverTrackingState state;
  final String orderId;
  final Future<void> Function() onMarkDelivered;

  @override
  Widget build(BuildContext context) {
    final dest = state.destination ?? const MapPoint(lat: 0, lng: 0);
    return Column(
      children: [
        Expanded(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.s3),
            child: MapboxDeliveryMap(
              driverLocation: state.driverLocation,
              destination: dest,
              breadcrumb: state.breadcrumb,
            ),
          ),
        ),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.s3),
          child: AppCard(
            child: Padding(
              padding: const EdgeInsets.all(AppSpacing.s3),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Order #${orderId.substring(0, orderId.length.clamp(0, 8))}',
                    style: context.textStyles.labelMedium?.copyWith(
                      color: context.colors.onSurfaceVariant,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.s1),
                  Text(
                    statusHeadline(state.status),
                    style: context.textStyles.titleMedium,
                  ),
                  if (state.etaSeconds != null) ...[
                    const SizedBox(height: AppSpacing.s1),
                    Text(
                      etaCopy(state.etaSeconds),
                      style: context.textStyles.bodyMedium,
                    ),
                  ],
                  const SizedBox(height: AppSpacing.s3),
                  if (state.status == TrackingDeliveryStatus.outForDelivery)
                    FilledButton.icon(
                      icon: const Icon(Icons.check_circle),
                      label: const Text('Mark delivered'),
                      onPressed: () => onMarkDelivered(),
                    ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
