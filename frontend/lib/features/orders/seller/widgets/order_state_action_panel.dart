import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../app/theme/tokens.dart';
import '../../../../data/api/api_client.dart';
import '../../../../shared/widgets/app_button.dart';
import '../../../../shared/widgets/app_snackbar.dart';
import '../../data/order_dtos.dart';
import '../../state/order_controller.dart';

/// State-machine action descriptor.
class OrderAction {
  const OrderAction({
    required this.label,
    required this.action,
    this.destructive = false,
  });
  final String label;
  final String action;
  final bool destructive;
}

/// Pure function: from an order's current status, return the actions the
/// seller may perform. Kept pure for unit testing.
List<OrderAction> orderActionsForStatus(String status) {
  switch (status) {
    case 'pending':
      return const [
        OrderAction(label: 'Accept', action: 'accept'),
        OrderAction(label: 'Cancel', action: 'cancel', destructive: true),
      ];
    case 'accepted':
      return const [
        OrderAction(label: 'Start preparing', action: 'preparing'),
        OrderAction(label: 'Cancel', action: 'cancel', destructive: true),
      ];
    case 'preparing':
      return const [
        OrderAction(label: 'Self-deliver', action: 'self-deliver'),
        OrderAction(label: 'Request a driver', action: 'request-driver'),
      ];
    case 'out_for_delivery':
      return const [
        OrderAction(label: 'Mark delivered', action: 'delivered'),
      ];
    case 'delivered':
      return const [
        OrderAction(label: 'Complete order', action: 'complete'),
      ];
    case 'self_delivering':
      return const [
        OrderAction(label: 'Out for delivery', action: 'out-for-delivery'),
      ];
    default:
      return const [];
  }
}

/// Provider that returns actions for a given status. Used by tests and by
/// the action panel widget below.
final orderStateActionsProvider =
    Provider.family<List<OrderAction>, String>((ref, status) {
  return orderActionsForStatus(status);
});

class OrderStateActionPanel extends ConsumerStatefulWidget {
  const OrderStateActionPanel({super.key, required this.order});
  final OrderResponse order;

  @override
  ConsumerState<OrderStateActionPanel> createState() =>
      _OrderStateActionPanelState();
}

class _OrderStateActionPanelState
    extends ConsumerState<OrderStateActionPanel> {
  bool _busy = false;

  Future<void> _invoke(OrderAction a) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      await ref
          .read(sellerOrdersControllerProvider.notifier)
          .transition(widget.order.id, a.action);
      if (mounted) {
        context.showAppSnackbar(message: 'Order updated');
      }
    } on ApiException catch (e) {
      if (!mounted) return;
      if (e.isConflict && e.isDeliveryAlreadyStarted) {
        // ADR-0003: idempotent — already in desired state; state refreshed.
        context.showAppSnackbar(message: 'Already out for delivery');
      } else {
        context.showAppSnackbar(message: e.message ?? 'Could not update order');
      }
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final actions =
        ref.watch(orderStateActionsProvider(widget.order.status));
    if (actions.isEmpty) return const SizedBox.shrink();
    return Wrap(
      spacing: AppSpacing.s2,
      runSpacing: AppSpacing.s2,
      children: [
        for (final a in actions)
          AppButton(
            label: a.label,
            variant: a.destructive
                ? AppButtonVariant.destructive
                : AppButtonVariant.primary,
            onPressed: _busy ? null : () => _invoke(a),
          ),
      ],
    );
  }
}
