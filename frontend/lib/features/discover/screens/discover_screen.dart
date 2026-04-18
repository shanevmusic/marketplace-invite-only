import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../products/data/product_dtos.dart';
import '../state/discover_controller.dart';
import '../state/discover_state.dart';

class DiscoverScreen extends ConsumerWidget {
  const DiscoverScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(discoverControllerProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => AppEmptyState(
        icon: Icons.error_outline,
        headline: 'Something went wrong',
        subhead: '$e',
        ctaLabel: 'Retry',
        onCtaPressed: () =>
            ref.read(discoverControllerProvider.notifier).refresh(),
      ),
      data: (state) => _renderState(context, ref, state),
    );
  }

  Widget _renderState(
      BuildContext context, WidgetRef ref, CustomerDiscoverState s) {
    switch (s) {
      case DiscoverUnreferred():
        return const AppEmptyState(
          icon: Icons.lock_outline,
          headline: 'You need a seller invite',
          subhead:
              'This marketplace is invite-only. Ask a seller for their referral link, then open it to unlock their store.',
          ctaLabel: 'How invites work',
        );
      case DiscoverLoading():
        return const Center(child: CircularProgressIndicator());
      case DiscoverSellerProfileMissing():
        return AppEmptyState(
          icon: Icons.storefront_outlined,
          headline: 'Seller unavailable',
          subhead: 'This seller is not active right now.',
          ctaLabel: 'Retry',
          onCtaPressed: () =>
              ref.read(discoverControllerProvider.notifier).refresh(),
        );
      case DiscoverNoProducts(seller: final seller):
        return AppEmptyState(
          icon: Icons.inventory_2_outlined,
          headline: 'No products yet',
          subhead: '${seller.displayName} has no products right now.',
        );
      case DiscoverReady(seller: final seller, products: final products):
        return _ReadyView(seller: seller.displayName, products: products);
      case DiscoverError(message: final msg):
        return AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Something went wrong',
          subhead: msg,
          ctaLabel: 'Retry',
          onCtaPressed: () =>
              ref.read(discoverControllerProvider.notifier).refresh(),
        );
    }
  }
}

class _ReadyView extends StatelessWidget {
  const _ReadyView({required this.seller, required this.products});
  final String seller;
  final List<ProductResponse> products;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.s4),
      children: [
        Text('Shop from $seller', style: context.textStyles.headlineSmall),
        const SizedBox(height: AppSpacing.s3),
        GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            crossAxisSpacing: AppSpacing.s3,
            mainAxisSpacing: AppSpacing.s3,
            childAspectRatio: 0.75,
          ),
          itemCount: products.length,
          itemBuilder: (_, i) {
            final p = products[i];
            return AppCard(
              variant: AppCardVariant.interactive,
              onTap: () => context.go(
                '${AppRoutes.customerDiscover}/product/${p.id}',
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Expanded(
                    child: Container(
                      decoration: BoxDecoration(
                        color: context.colors.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(AppRadius.sm),
                      ),
                      alignment: Alignment.center,
                      child: Icon(
                        Icons.image_outlined,
                        color: context.colors.onSurfaceVariant,
                        size: 32,
                      ),
                    ),
                  ),
                  const SizedBox(height: AppSpacing.s2),
                  Text(p.name,
                      style: context.textStyles.titleSmall,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis),
                  const SizedBox(height: AppSpacing.s1),
                  Text(
                    formatMoney(p.priceMinor, currencyCode: p.currencyCode),
                    style: context.textStyles.bodyMedium,
                  ),
                ],
              ),
            );
          },
        ),
      ],
    );
  }
}
