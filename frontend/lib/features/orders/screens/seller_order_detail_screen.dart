import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/order_status_chip.dart';
import '../../../shared/widgets/order_status_timeline.dart';
import '../seller/widgets/order_state_action_panel.dart';
import '../state/order_controller.dart';

class SellerOrderDetailScreen extends ConsumerWidget {
  const SellerOrderDetailScreen({super.key, required this.orderId});
  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(orderByIdProvider(orderId));
    return Scaffold(
      appBar: AppTopBar(title: 'Order'),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Could not load order',
        ),
        data: (o) {
          return ListView(
            padding: const EdgeInsets.all(AppSpacing.s4),
            children: [
              AppCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Order #${o.id.substring(0, 8)}',
                            style: context.textStyles.titleLarge,
                          ),
                        ),
                        OrderStatusChip(status: o.status),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.s2),
                    Text(
                      o.deliveryAddress.oneLine(),
                      style: context.textStyles.bodyMedium?.copyWith(
                        color: context.colors.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
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
                    Text('Items', style: context.textStyles.titleMedium),
                    const SizedBox(height: AppSpacing.s2),
                    for (final it in o.items)
                      Padding(
                        padding: const EdgeInsets.only(bottom: AppSpacing.s2),
                        child: Row(
                          children: [
                            Expanded(child: Text('${it.quantity}× ${it.name}')),
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
                                style: context.textStyles.titleMedium)),
                        Text(
                            formatMoney(o.totalMinor,
                                currencyCode: o.currencyCode),
                            style: context.textStyles.titleMedium),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.s4),
              OrderStateActionPanel(order: o),
            ],
          );
        },
      ),
    );
  }
}
