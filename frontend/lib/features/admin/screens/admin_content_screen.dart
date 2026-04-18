import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_dialog.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_list_tile.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../data/admin_dtos.dart';
import '../state/admin_controllers.dart';

class AdminContentScreen extends ConsumerStatefulWidget {
  const AdminContentScreen({super.key});

  @override
  ConsumerState<AdminContentScreen> createState() => _AdminContentScreenState();
}

class _AdminContentScreenState extends ConsumerState<AdminContentScreen> {
  final TextEditingController _search = TextEditingController();
  String? _status;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _apply() {
    ref.read(adminProductsControllerProvider.notifier).applyFilter(
          AdminProductsFilter(
            q: _search.text.trim().isEmpty ? null : _search.text.trim(),
            status: _status,
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(adminProductsControllerProvider);
    return Scaffold(
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.s4),
            child: AppTextField(
              controller: _search,
              label: 'Search products',
              onSubmitted: (_) => _apply(),
            ),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s4),
            child: DropdownButton<String?>(
              isExpanded: true,
              value: _status,
              hint: const Text('All statuses'),
              items: const [
                DropdownMenuItem(value: null, child: Text('All statuses')),
                DropdownMenuItem(value: 'active', child: Text('Active')),
                DropdownMenuItem(value: 'disabled', child: Text('Disabled')),
                DropdownMenuItem(
                    value: 'out_of_stock', child: Text('Out of stock')),
              ],
              onChanged: (v) {
                setState(() => _status = v);
                _apply();
              },
            ),
          ),
          Expanded(
            child: async.when(
              loading: () =>
                  const Center(child: CircularProgressIndicator()),
              error: (e, _) => AppEmptyState(
                icon: Icons.error_outline,
                headline: "Can't load products",
                subhead: '$e',
              ),
              data: (s) {
                if (s.products.isEmpty) {
                  return const AppEmptyState(
                    icon: Icons.inventory_2_outlined,
                    headline: 'No products match this filter.',
                  );
                }
                return ListView.builder(
                  itemCount: s.products.length,
                  itemBuilder: (context, i) {
                    final p = s.products[i];
                    return AppListTile(
                      title: p.name,
                      subtitle: formatMoney(p.priceMinor),
                      trailing: _ProductStatusChip(status: p.status),
                      onTap: () => _showProductSheet(context, ref, p),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}

class _ProductStatusChip extends StatelessWidget {
  const _ProductStatusChip({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    Color bg;
    Color fg;
    switch (status) {
      case 'disabled':
        bg = colors.errorContainer;
        fg = colors.onErrorContainer;
        break;
      case 'out_of_stock':
        bg = colors.tertiaryContainer;
        fg = colors.onTertiaryContainer;
        break;
      default:
        bg = colors.surfaceContainerHighest;
        fg = colors.onSurface;
    }
    return Container(
      padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s2, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Text(status.toUpperCase(),
          style: context.textStyles.labelSmall?.copyWith(color: fg)),
    );
  }
}

Future<void> _showProductSheet(
    BuildContext context, WidgetRef ref, AdminProductSummary p) async {
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) {
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.s4),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(p.name, style: context.textStyles.headlineSmall),
              const SizedBox(height: AppSpacing.s2),
              Text(formatMoney(p.priceMinor),
                  style: context.textStyles.titleMedium),
              const SizedBox(height: AppSpacing.s2),
              _ProductStatusChip(status: p.status),
              if (p.disabledReason != null) ...[
                const SizedBox(height: AppSpacing.s3),
                Text('Disabled reason',
                    style: context.textStyles.labelSmall),
                Text(p.disabledReason!,
                    style: context.textStyles.bodyMedium),
              ],
              const SizedBox(height: AppSpacing.s4),
              if (p.status == 'disabled')
                AppButton(
                  label: 'Restore product',
                  onPressed: () async {
                    await ref
                        .read(adminProductsControllerProvider.notifier)
                        .restore(p.id);
                    if (context.mounted) {
                      Navigator.of(context).pop();
                      context.showAppSnackbar(
                          message: 'Product restored.');
                    }
                  },
                )
              else
                AppButton(
                  label: 'Disable product',
                  variant: AppButtonVariant.destructive,
                  onPressed: () => _promptDisable(context, ref, p.id),
                ),
            ],
          ),
        ),
      );
    },
  );
}

Future<void> _promptDisable(
    BuildContext context, WidgetRef ref, String id) async {
  final controller = TextEditingController();
  await AppDialog.show(
    context,
    title: 'Disable product?',
    body: AppTextField(
      controller: controller,
      label: 'Reason',
      hint: 'Required (1–500 chars)',
    ),
    primaryAction: AppDialogAction(
      label: 'Disable',
      destructive: true,
      onPressed: () async {
        final reason = controller.text.trim();
        if (reason.isEmpty) return;
        Navigator.of(context).pop();
        await ref
            .read(adminProductsControllerProvider.notifier)
            .disable(id, reason);
        if (context.mounted) {
          Navigator.of(context).pop();
          context.showAppSnackbar(message: 'Product disabled.');
        }
      },
    ),
    secondaryAction: AppDialogAction(
      label: 'Cancel',
      onPressed: () => Navigator.of(context).pop(),
    ),
  );
}
