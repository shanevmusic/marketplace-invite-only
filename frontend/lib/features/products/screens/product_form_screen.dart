import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../../../shared/widgets/money_field.dart';
import '../data/product_dtos.dart';
import '../state/product_controller.dart';

class ProductFormScreen extends ConsumerStatefulWidget {
  const ProductFormScreen({super.key, this.existing});
  final ProductResponse? existing;

  @override
  ConsumerState<ProductFormScreen> createState() => _ProductFormScreenState();
}

class _ProductFormScreenState extends ConsumerState<ProductFormScreen> {
  late final TextEditingController _name;
  late final TextEditingController _desc;
  late final TextEditingController _stock;
  int? _priceMinor;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _name = TextEditingController(text: widget.existing?.name ?? '');
    _desc = TextEditingController(text: widget.existing?.description ?? '');
    _stock = TextEditingController(
      text: widget.existing != null ? '${widget.existing!.stockQuantity}' : '0',
    );
    _priceMinor = widget.existing?.priceMinor;
  }

  @override
  void dispose() {
    _name.dispose();
    _desc.dispose();
    _stock.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_name.text.trim().isEmpty || (_priceMinor ?? 0) <= 0) {
      context.showAppSnackbar(
          message: 'Name and a positive price are required');
      return;
    }
    setState(() => _busy = true);
    try {
      final stock = int.tryParse(_stock.text.trim()) ?? 0;
      if (widget.existing == null) {
        await ref.read(myProductsControllerProvider.notifier).create(
              CreateProductRequest(
                name: _name.text.trim(),
                description:
                    _desc.text.trim().isEmpty ? null : _desc.text.trim(),
                priceMinor: _priceMinor!,
                stockQuantity: stock,
                images: const [],
              ),
            );
      } else {
        await ref.read(myProductsControllerProvider.notifier).updateProduct(
              widget.existing!.id,
              UpdateProductRequest(
                name: _name.text.trim(),
                description: _desc.text.trim(),
                priceMinor: _priceMinor,
                stockQuantity: stock,
              ),
            );
      }
      if (!mounted) return;
      context.go(AppRoutes.sellerProducts);
    } catch (e) {
      if (mounted) context.showAppSnackbar(message: 'Could not save product');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<void> _delete() async {
    if (widget.existing == null) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(myProductsControllerProvider.notifier)
          .delete(widget.existing!.id);
      if (!mounted) return;
      context.go(AppRoutes.sellerProducts);
    } catch (_) {
      if (mounted) context.showAppSnackbar(message: 'Could not delete');
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final editing = widget.existing != null;
    return Scaffold(
      appBar: AppTopBar(title: editing ? 'Edit product' : 'New product'),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(AppSpacing.s4),
          children: [
            AppTextField(label: 'Name', controller: _name),
            const SizedBox(height: AppSpacing.s3),
            AppTextField(label: 'Description', controller: _desc),
            const SizedBox(height: AppSpacing.s3),
            MoneyField(
              initialMinor: _priceMinor,
              onChanged: (v) => setState(() => _priceMinor = v),
              label: 'Price',
            ),
            const SizedBox(height: AppSpacing.s3),
            AppTextField(
              label: 'Stock',
              controller: _stock,
              kind: AppTextFieldKind.numeric,
            ),
            // Phase 12: presigned upload flow lives in
            // `product_image_service.dart` (presign → PUT → confirm). The
            // image_picker UI is phase-13; form currently submits an empty
            // list which the backend accepts.
            const SizedBox(height: AppSpacing.s5),
            AppButton(
              label: editing ? 'Save changes' : 'Create product',
              isLoading: _busy,
              expand: true,
              onPressed: _busy ? null : _submit,
            ),
            if (editing) ...[
              const SizedBox(height: AppSpacing.s3),
              AppButton(
                label: 'Delete product',
                variant: AppButtonVariant.destructive,
                expand: true,
                onPressed: _busy ? null : _delete,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
