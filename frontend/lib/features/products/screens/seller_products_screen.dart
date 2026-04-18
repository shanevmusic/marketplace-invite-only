import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../state/product_controller.dart';

class SellerProductsScreen extends ConsumerWidget {
  const SellerProductsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final listAsync = ref.watch(myProductsControllerProvider);
    return Scaffold(
      floatingActionButton: FloatingActionButton.extended(
        icon: const Icon(Icons.add),
        label: const Text('New product'),
        onPressed: () => context.go('${AppRoutes.sellerProducts}/new'),
      ),
      body: listAsync.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Could not load products',
          ctaLabel: 'Retry',
          onCtaPressed: () =>
              ref.read(myProductsControllerProvider.notifier).refresh(),
        ),
        data: (items) {
          if (items.isEmpty) {
            return AppEmptyState(
              icon: Icons.inventory_2_outlined,
              headline: 'No products yet',
              subhead: 'Add your first product to start selling.',
              ctaLabel: 'Add product',
              onCtaPressed: () =>
                  context.go('${AppRoutes.sellerProducts}/new'),
            );
          }
          return RefreshIndicator(
            onRefresh: () =>
                ref.read(myProductsControllerProvider.notifier).refresh(),
            child: ListView.separated(
              padding: const EdgeInsets.all(AppSpacing.s4),
              itemCount: items.length,
              separatorBuilder: (_, __) =>
                  const SizedBox(height: AppSpacing.s3),
              itemBuilder: (_, i) {
                final p = items[i];
                return AppCard(
                  variant: AppCardVariant.interactive,
                  onTap: () =>
                      context.go('${AppRoutes.sellerProducts}/${p.id}/edit'),
                  child: Row(
                    children: [
                      Container(
                        width: 56,
                        height: 56,
                        decoration: BoxDecoration(
                          color: context.colors.surfaceContainerHighest,
                          borderRadius:
                              BorderRadius.circular(AppRadius.sm),
                        ),
                        alignment: Alignment.center,
                        child: Icon(Icons.inventory_2_outlined,
                            color: context.colors.onSurfaceVariant),
                      ),
                      const SizedBox(width: AppSpacing.s3),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(p.name,
                                style: context.textStyles.titleMedium),
                            const SizedBox(height: AppSpacing.s1),
                            Text(
                              '${formatMoney(p.priceMinor, currencyCode: p.currencyCode)} · ${p.stockQuantity} in stock',
                              style: context.textStyles.bodySmall?.copyWith(
                                color: context.colors.onSurfaceVariant,
                              ),
                            ),
                          ],
                        ),
                      ),
                      if (!p.isActive)
                        Padding(
                          padding: const EdgeInsets.only(left: AppSpacing.s2),
                          child: Text('Inactive',
                              style: context.textStyles.labelSmall?.copyWith(
                                color: context.colors.onSurfaceVariant,
                              )),
                        ),
                    ],
                  ),
                );
              },
            ),
          );
        },
      ),
    );
  }
}
