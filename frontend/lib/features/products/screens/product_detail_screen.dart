import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../../../shared/widgets/image_gallery.dart';
import '../../../shared/widgets/quantity_stepper.dart';
import '../../cart/cart_store.dart';
import '../state/product_controller.dart';

class ProductDetailScreen extends ConsumerStatefulWidget {
  const ProductDetailScreen({super.key, required this.productId});
  final String productId;

  @override
  ConsumerState<ProductDetailScreen> createState() =>
      _ProductDetailScreenState();
}

class _ProductDetailScreenState extends ConsumerState<ProductDetailScreen> {
  int _qty = 1;

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(productByIdProvider(widget.productId));
    return Scaffold(
      appBar: AppTopBar(title: 'Product'),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Could not load product',
        ),
        data: (p) {
          final imgs = p.images.map((e) => e.s3Key).toList();
          return ListView(
            children: [
              ImageGallery(imageUrls: imgs),
              Padding(
                padding: const EdgeInsets.all(AppSpacing.s4),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(p.name, style: context.textStyles.headlineSmall),
                    const SizedBox(height: AppSpacing.s2),
                    Text(
                      formatMoney(p.priceMinor, currencyCode: p.currencyCode),
                      style: context.textStyles.titleLarge,
                    ),
                    const SizedBox(height: AppSpacing.s3),
                    if (p.description.isNotEmpty) ...[
                      Text(p.description, style: context.textStyles.bodyMedium),
                      const SizedBox(height: AppSpacing.s4),
                    ],
                    Row(
                      children: [
                        const Text('Quantity'),
                        const SizedBox(width: AppSpacing.s3),
                        QuantityStepper(
                          value: _qty,
                          min: 1,
                          max: p.stockQuantity > 0 ? p.stockQuantity : 99,
                          onChanged: (v) => setState(() => _qty = v),
                        ),
                      ],
                    ),
                    const SizedBox(height: AppSpacing.s5),
                    AppButton(
                      label: 'Add to cart',
                      expand: true,
                      onPressed: p.stockQuantity <= 0
                          ? null
                          : () async {
                              await ref
                                  .read(cartControllerProvider.notifier)
                                  .addLine(
                                    sellerId: p.sellerId,
                                    storeName: '',
                                    currencyCode: p.currencyCode,
                                    line: CartLine(
                                      productId: p.id,
                                      name: p.name,
                                      unitPriceMinor: p.priceMinor,
                                      quantity: _qty,
                                      imageKey: p.primaryImageKey,
                                      stockQuantity: p.stockQuantity,
                                    ),
                                  );
                              if (context.mounted) {
                                context.showAppSnackbar(
                                    message: 'Added to cart');
                              }
                            },
                    ),
                  ],
                ),
              ),
            ],
          );
        },
      ),
    );
  }
}
