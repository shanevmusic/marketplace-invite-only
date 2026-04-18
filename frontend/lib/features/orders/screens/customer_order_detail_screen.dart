import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/order_status_timeline.dart';
import '../customer/widgets/customer_order_delivery_status.dart';
import '../state/order_controller.dart';

class CustomerOrderDetailScreen extends ConsumerWidget {
  const CustomerOrderDetailScreen({super.key, required this.orderId});
  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(customerOrderDetailProvider(orderId));
    return Scaffold(
      appBar: AppTopBar(title: 'Your order'),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Could not load order',
        ),
        data: (o) {
          final props = CustomerOrderDeliveryProps.fromOrder(o);
          return RefreshIndicator(
            onRefresh: () => ref
                .read(customerOrderDetailProvider(orderId).notifier)
                .refreshNow(),
            child: ListView(
              padding: const EdgeInsets.all(AppSpacing.s4),
              children: [
                CustomerDeliveryStatusWidget(props: props),
                const SizedBox(height: AppSpacing.s4),
                OrderStatusTimeline(
                  currentStatus: o.status,
                  placedAt: o.createdAt,
                ),
                const SizedBox(height: AppSpacing.s4),
                AppCard(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Items',
                          style: context.textStyles.titleMedium),
                      const SizedBox(height: AppSpacing.s2),
                      for (final it in o.items)
                        Padding(
                          padding:
                              const EdgeInsets.only(bottom: AppSpacing.s2),
                          child: Row(
                            children: [
                              Expanded(
                                  child:
                                      Text('${it.quantity}× ${it.name}')),
                              Text(formatMoney(it.lineTotalMinor,
                                  currencyCode: o.currencyCode)),
                            ],
                          ),
                        ),
                      const Divider(),
                      Row(
                        children: [
                          Expanded(
                            child: Text('Total',
                                style: context.textStyles.titleMedium),
                          ),
                          Text(
                            formatMoney(o.totalMinor,
                                currencyCode: o.currencyCode),
                            style: context.textStyles.titleMedium,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
