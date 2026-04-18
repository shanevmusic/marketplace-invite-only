import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/quantity_stepper.dart';
import '../cart_store.dart';

class CartScreen extends ConsumerWidget {
  const CartScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(cartControllerProvider);
    return Scaffold(
      appBar: AppTopBar(title: 'Cart'),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Could not load cart',
        ),
        data: (state) {
          if (state.buckets.isEmpty) {
            return const AppEmptyState(
              icon: Icons.shopping_cart_outlined,
              headline: 'Your cart is empty',
              subhead: 'Add products from a seller to get started.',
            );
          }
          return ListView(
            padding: const EdgeInsets.all(AppSpacing.s4),
            children: [
              for (final bucket in state.buckets.values) ...[
                Text(
                  bucket.storeName.isEmpty ? 'Seller order' : bucket.storeName,
                  style: context.textStyles.titleMedium,
                ),
                const SizedBox(height: AppSpacing.s2),
                for (final line in bucket.lines)
                  AppCard(
                    child: Row(
                      children: [
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(line.name,
                                  style: context.textStyles.titleSmall),
                              const SizedBox(height: AppSpacing.s1),
                              Text(formatMoney(line.unitPriceMinor,
                                  currencyCode: bucket.currencyCode)),
                            ],
                          ),
                        ),
                        QuantityStepper(
                          value: line.quantity,
                          min: 0,
                          max: line.stockQuantity ?? 99,
                          onChanged: (v) => ref
                              .read(cartControllerProvider.notifier)
                              .updateQuantity(
                                sellerId: bucket.sellerId,
                                productId: line.productId,
                                quantity: v,
                              ),
                        ),
                      ],
                    ),
                  ),
                const SizedBox(height: AppSpacing.s3),
                Row(
                  children: [
                    Expanded(
                      child: Text('Subtotal',
                          style: context.textStyles.titleMedium),
                    ),
                    Text(
                      formatMoney(bucket.subtotalMinor,
                          currencyCode: bucket.currencyCode),
                      style: context.textStyles.titleMedium,
                    ),
                  ],
                ),
                const SizedBox(height: AppSpacing.s3),
                AppButton(
                  label: 'Checkout',
                  expand: true,
                  onPressed: () => context.go(
                    '/checkout/${bucket.sellerId}',
                  ),
                ),
                const SizedBox(height: AppSpacing.s5),
              ],
            ],
          );
        },
      ),
    );
  }
}
