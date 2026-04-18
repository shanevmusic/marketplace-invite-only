import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/order_status_chip.dart';
import '../state/order_controller.dart';

class SellerOrdersScreen extends ConsumerWidget {
  const SellerOrdersScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(sellerOrdersControllerProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, __) => AppEmptyState(
        icon: Icons.error_outline,
        headline: 'Could not load orders',
        ctaLabel: 'Retry',
        onCtaPressed: () =>
            ref.read(sellerOrdersControllerProvider.notifier).refresh(),
      ),
      data: (orders) {
        if (orders.isEmpty) {
          return const AppEmptyState(
            icon: Icons.receipt_long_outlined,
            headline: 'No orders yet',
            subhead: 'Orders from your customers will appear here.',
          );
        }
        return RefreshIndicator(
          onRefresh: () =>
              ref.read(sellerOrdersControllerProvider.notifier).refresh(),
          child: ListView.separated(
            padding: const EdgeInsets.all(AppSpacing.s4),
            itemCount: orders.length,
            separatorBuilder: (_, __) =>
                const SizedBox(height: AppSpacing.s3),
            itemBuilder: (_, i) {
              final o = orders[i];
              return AppCard(
                variant: AppCardVariant.interactive,
                onTap: () =>
                    context.go('${AppRoutes.sellerOrders}/${o.id}'),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'Order #${o.id.substring(0, 8)}',
                            style: context.textStyles.titleMedium,
                          ),
                        ),
                        OrderStatusChip(status: o.status),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.s1),
                    Text(
                      '${o.items.length} item(s) · ${formatMoney(o.totalMinor, currencyCode: o.currencyCode)}',
                      style: context.textStyles.bodySmall?.copyWith(
                        color: context.colors.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        );
      },
    );
  }
}
