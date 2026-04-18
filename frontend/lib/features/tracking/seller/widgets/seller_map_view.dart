import 'package:flutter/material.dart';

import '../../../../app/theme/theme_extensions.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../_internal_shared/mapbox_delivery_map.dart';
import '../../shared/delivery_status.dart';
import '../application/seller_tracking_controller.dart';

class SellerMapView extends StatelessWidget {
  const SellerMapView({
    super.key,
    required this.state,
    required this.orderId,
  });

  final SellerTrackingState state;
  final String orderId;

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
              followDriver: false,
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
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}
