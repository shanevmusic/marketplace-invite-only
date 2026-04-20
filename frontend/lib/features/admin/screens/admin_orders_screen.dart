import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_list_tile.dart';
import '../data/admin_dtos.dart';
import '../state/admin_controllers.dart';

/// Admin → Orders tab.  Lists every order across the platform with a
/// status filter.  Lightweight by design: shows order id (short), status,
/// total, and placed-at timestamp.  Detailed order views live in the
/// seller / customer order screens; admins navigate there directly via
/// the user detail sheet.
class AdminOrdersScreen extends ConsumerStatefulWidget {
  const AdminOrdersScreen({super.key});

  @override
  ConsumerState<AdminOrdersScreen> createState() => _AdminOrdersScreenState();
}

class _AdminOrdersScreenState extends ConsumerState<AdminOrdersScreen> {
  String? _status;

  void _apply() {
    ref
        .read(adminOrdersControllerProvider.notifier)
        .applyFilter(AdminOrdersFilter(status: _status));
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(adminOrdersControllerProvider);
    return Scaffold(
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.s4),
            child: DropdownButton<String?>(
              isExpanded: true,
              value: _status,
              hint: const Text('All statuses'),
              items: const [
                DropdownMenuItem(value: null, child: Text('All statuses')),
                DropdownMenuItem(value: 'pending', child: Text('Pending')),
                DropdownMenuItem(value: 'accepted', child: Text('Accepted')),
                DropdownMenuItem(
                    value: 'preparing', child: Text('Preparing')),
                DropdownMenuItem(
                    value: 'out_for_delivery',
                    child: Text('Out for delivery')),
                DropdownMenuItem(
                    value: 'delivered', child: Text('Delivered')),
                DropdownMenuItem(
                    value: 'completed', child: Text('Completed')),
                DropdownMenuItem(
                    value: 'cancelled', child: Text('Cancelled')),
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
                headline: "Can't load orders",
                subhead: '$e',
              ),
              data: (s) => _OrdersList(state: s),
            ),
          ),
        ],
      ),
    );
  }
}

class _OrdersList extends ConsumerWidget {
  const _OrdersList({required this.state});
  final AdminOrdersState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (state.orders.isEmpty) {
      return const AppEmptyState(
        icon: Icons.receipt_long_outlined,
        headline: 'No orders match this filter.',
      );
    }
    return NotificationListener<ScrollNotification>(
      onNotification: (n) {
        if (n.metrics.pixels >= n.metrics.maxScrollExtent - 200) {
          ref.read(adminOrdersControllerProvider.notifier).loadMore();
        }
        return false;
      },
      child: ListView.builder(
        itemCount: state.orders.length + (state.isLoadingMore ? 1 : 0),
        itemBuilder: (context, i) {
          if (i >= state.orders.length) {
            return const Padding(
              padding: EdgeInsets.all(AppSpacing.s4),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          final o = state.orders[i];
          final shortId = o.id.length >= 8 ? o.id.substring(0, 8) : o.id;
          return AppListTile(
            leading: const CircleAvatar(
              child: Icon(Icons.receipt_long_outlined),
            ),
            title: 'Order $shortId',
            subtitle: _formatTimestamp(o.placedAt),
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(formatMoney(o.totalMinor),
                    style: context.textStyles.titleSmall),
                const SizedBox(width: AppSpacing.s2),
                _OrderStatusChip(status: o.status),
              ],
            ),
          );
        },
      ),
    );
  }

  String _formatTimestamp(DateTime dt) {
    final local = dt.toLocal();
    final iso = local.toIso8601String();
    // YYYY-MM-DD HH:MM
    return '${iso.substring(0, 10)} ${iso.substring(11, 16)}';
  }
}

class _OrderStatusChip extends StatelessWidget {
  const _OrderStatusChip({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final (bg, fg) = _palette(colors, status);
    return Container(
      padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s2, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Text(
        _label(status),
        style: context.textStyles.labelSmall?.copyWith(color: fg),
      ),
    );
  }

  static String _label(String s) {
    switch (s) {
      case 'out_for_delivery':
        return 'OUT FOR DELIVERY';
      default:
        return s.toUpperCase();
    }
  }

  static (Color, Color) _palette(ColorScheme c, String status) {
    switch (status) {
      case 'cancelled':
        return (c.errorContainer, c.onErrorContainer);
      case 'completed':
      case 'delivered':
        return (c.primaryContainer, c.onPrimaryContainer);
      default:
        return (c.surfaceContainerHighest, c.onSurface);
    }
  }
}
