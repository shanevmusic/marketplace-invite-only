import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../shared/widgets/app_app_bar.dart';
import '../application/seller_tracking_controller.dart';
import '../widgets/seller_map_view.dart';

class SellerTrackingScreen extends ConsumerWidget {
  const SellerTrackingScreen({super.key, required this.orderId});
  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(sellerTrackingControllerProvider(orderId));
    return Scaffold(
      appBar: AppTopBar(title: 'Delivery tracking'),
      body: SellerMapView(state: state, orderId: orderId),
    );
  }
}
