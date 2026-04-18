// ADR-0014: This file lives under _internal_shared/ and is imported ONLY by
// driver/ and seller/. An import boundary test forbids customer/ from
// referencing anything in this directory or mapbox_maps_flutter.
//
// V1 ships a placeholder widget. The real Mapbox SDK wiring (tile layer,
// driver pin, destination pin, breadcrumb polyline) is behind this widget's
// API so the call sites don't change when the SDK is wired up.
import 'package:flutter/material.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';

class MapPoint {
  const MapPoint({required this.lat, required this.lng});
  final double lat;
  final double lng;
}

class MapboxDeliveryMap extends StatelessWidget {
  const MapboxDeliveryMap({
    super.key,
    required this.driverLocation,
    required this.destination,
    this.breadcrumb = const [],
    this.followDriver = true,
  });

  final MapPoint? driverLocation;
  final MapPoint destination;
  final List<MapPoint> breadcrumb;
  final bool followDriver;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: context.colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.map_outlined,
              size: 48,
              color: context.colors.onSurfaceVariant,
            ),
            const SizedBox(height: AppSpacing.s2),
            Text(
              driverLocation == null
                  ? 'Waiting for driver location…'
                  : 'Driver · ${driverLocation!.lat.toStringAsFixed(4)}, ${driverLocation!.lng.toStringAsFixed(4)}',
              style: context.textStyles.labelMedium,
            ),
            const SizedBox(height: AppSpacing.s1),
            Text(
              'Destination · ${destination.lat.toStringAsFixed(4)}, ${destination.lng.toStringAsFixed(4)}',
              style: context.textStyles.labelSmall?.copyWith(
                color: context.colors.onSurfaceVariant,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
