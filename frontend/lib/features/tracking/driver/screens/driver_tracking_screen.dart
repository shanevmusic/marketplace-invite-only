import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/app_app_bar.dart';
import '../application/driver_tracking_controller.dart';
import '../widgets/driver_map_view.dart';

class DriverTrackingScreen extends ConsumerWidget {
  const DriverTrackingScreen({super.key, required this.orderId});
  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(driverTrackingControllerProvider(orderId));
    return Scaffold(
      appBar: AppTopBar(title: 'Delivery'),
      body: DriverMapView(
        state: state,
        orderId: orderId,
        onMarkDelivered: () async {
          try {
            await ref
                .read(driverTrackingControllerProvider(orderId).notifier)
                .markDelivered();
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text('Delivered')),
              );
            }
          } catch (_) {
            if (context.mounted) {
              ScaffoldMessenger.of(context).showSnackBar(
                const SnackBar(content: Text("Couldn't mark delivered")),
              );
            }
          }
        },
      ),
    );
  }
}
