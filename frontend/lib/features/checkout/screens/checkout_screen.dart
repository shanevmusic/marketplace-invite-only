import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../data/api/api_client.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../../cart/cart_store.dart';
import '../../orders/data/order_dtos.dart';
import '../../orders/state/order_controller.dart';

class CheckoutScreen extends ConsumerStatefulWidget {
  const CheckoutScreen({super.key, required this.sellerId});
  final String sellerId;

  @override
  ConsumerState<CheckoutScreen> createState() => _CheckoutScreenState();
}

class _CheckoutScreenState extends ConsumerState<CheckoutScreen> {
  final _line1 = TextEditingController();
  final _line2 = TextEditingController();
  final _city = TextEditingController();
  final _region = TextEditingController();
  final _postal = TextEditingController();
  final _country = TextEditingController(text: 'US');
  final _notes = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    for (final c in [_line1, _line2, _city, _region, _postal, _country, _notes]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _placeOrder(SellerCart bucket) async {
    if (_line1.text.trim().isEmpty || _city.text.trim().isEmpty) {
      context.showAppSnackbar(message: 'Address is required');
      return;
    }
    setState(() => _busy = true);
    try {
      final body = CreateOrderRequest(
        items: bucket.lines
            .map((l) => (productId: l.productId, quantity: l.quantity))
            .toList(),
        deliveryAddress: DeliveryAddress(
          line1: _line1.text.trim(),
          line2: _line2.text.trim().isEmpty ? null : _line2.text.trim(),
          city: _city.text.trim(),
          region: _region.text.trim().isEmpty ? null : _region.text.trim(),
          postal: _postal.text.trim().isEmpty ? null : _postal.text.trim(),
          country: _country.text.trim().toUpperCase(),
          notes: _notes.text.trim().isEmpty ? null : _notes.text.trim(),
        ),
      );
      final order = await ref.read(orderApiProvider).create(body);
      await ref
          .read(cartControllerProvider.notifier)
          .clearBucket(bucket.sellerId);
      ref.invalidate(customerOrdersControllerProvider);
      if (!mounted) return;
      context.go('${AppRoutes.customerOrders}/${order.id}');
    } on ApiException catch (e) {
      if (!mounted) return;
      final msg = e.isInsufficientStock
          ? 'Not enough stock for one of the items'
          : (e.message ?? 'Could not place order');
      context.showAppSnackbar(message: msg);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(cartControllerProvider);
    return Scaffold(
      appBar: AppTopBar(title: 'Checkout'),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Cart unavailable',
        ),
        data: (state) {
          final bucket = state.buckets[widget.sellerId];
          if (bucket == null) {
            return const AppEmptyState(
              icon: Icons.shopping_cart_outlined,
              headline: 'Nothing to check out',
            );
          }
          return ListView(
            padding: const EdgeInsets.all(AppSpacing.s4),
            children: [
              AppCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Summary',
                        style: context.textStyles.titleMedium),
                    const SizedBox(height: AppSpacing.s2),
                    for (final l in bucket.lines)
                      Padding(
                        padding:
                            const EdgeInsets.only(bottom: AppSpacing.s1),
                        child: Row(
                          children: [
                            Expanded(
                                child: Text('${l.quantity}× ${l.name}')),
                            Text(formatMoney(l.lineTotalMinor,
                                currencyCode: bucket.currencyCode)),
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
                          formatMoney(bucket.subtotalMinor,
                              currencyCode: bucket.currencyCode),
                          style: context.textStyles.titleMedium,
                        ),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.s4),
              Text('Delivery address',
                  style: context.textStyles.titleMedium),
              const SizedBox(height: AppSpacing.s2),
              AppTextField(label: 'Address line 1', controller: _line1),
              const SizedBox(height: AppSpacing.s2),
              AppTextField(label: 'Address line 2', controller: _line2),
              const SizedBox(height: AppSpacing.s2),
              AppTextField(label: 'City', controller: _city),
              const SizedBox(height: AppSpacing.s2),
              AppTextField(label: 'Region/State', controller: _region),
              const SizedBox(height: AppSpacing.s2),
              AppTextField(label: 'Postal code', controller: _postal),
              const SizedBox(height: AppSpacing.s2),
              AppTextField(label: 'Country code (ISO-2)', controller: _country),
              const SizedBox(height: AppSpacing.s2),
              AppTextField(label: 'Delivery notes', controller: _notes),
              const SizedBox(height: AppSpacing.s3),
              AppCard(
                child: Row(
                  children: [
                    Icon(Icons.lock_outline,
                        size: 16,
                        color: context.colors.onSurfaceVariant),
                    const SizedBox(width: AppSpacing.s2),
                    Expanded(
                      child: Text(
                        'Your coordinates are not shared with the seller. They see only your delivery address.',
                        style: context.textStyles.bodySmall?.copyWith(
                          color: context.colors.onSurfaceVariant,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: AppSpacing.s4),
              AppButton(
                label: 'Place order',
                expand: true,
                isLoading: _busy,
                onPressed: _busy ? null : () => _placeOrder(bucket),
              ),
            ],
          );
        },
      ),
    );
  }
}
