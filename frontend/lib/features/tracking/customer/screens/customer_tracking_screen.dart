// ADR-0014: customer-facing screen. Only imports from customer/ and shared/.
// MUST NOT import any driver/ or seller/ widgets, or _internal_shared/.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/app_app_bar.dart';
import '../../../../shared/widgets/app_empty_state.dart';
import '../../../orders/state/order_controller.dart';
import '../application/customer_tracking_controller.dart';
import '../widgets/customer_tracking_view.dart';

class CustomerTrackingScreen extends ConsumerWidget {
  const CustomerTrackingScreen({super.key, required this.orderId});
  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final orderAsync = ref.watch(customerOrderDetailProvider(orderId));
    final tracking = ref.watch(customerTrackingControllerProvider(orderId));

    return Scaffold(
      appBar: AppTopBar(title: 'Track order'),
      body: orderAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Could not load order',
        ),
        data: (order) {
          return CustomerTrackingView(
            props: CustomerTrackingProps(
              orderId: orderId,
              status: tracking.status,
              destinationLabel: order.deliveryAddress.oneLine(),
              etaSeconds: tracking.etaSeconds,
              etaUpdatedAt: tracking.etaUpdatedAt,
              lastUpdatedAt: tracking.lastUpdatedAt,
              sellerDisplayName: order.storeName,
            ),
          );
        },
      ),
    );
  }
}
