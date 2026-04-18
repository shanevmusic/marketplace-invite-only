import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

enum OrderStatusChipSize { sm, md }

class OrderStatusChip extends StatelessWidget {
  const OrderStatusChip({
    super.key,
    required this.status,
    this.size = OrderStatusChipSize.sm,
  });

  final String status;
  final OrderStatusChipSize size;

  static String humanLabel(String s) {
    switch (s) {
      case 'pending':
        return 'Pending';
      case 'accepted':
        return 'Accepted';
      case 'preparing':
        return 'Preparing';
      case 'out_for_delivery':
        return 'Out for delivery';
      case 'delivered':
        return 'Delivered';
      case 'completed':
        return 'Completed';
      case 'cancelled':
        return 'Cancelled';
      default:
        return s;
    }
  }

  static IconData iconFor(String s) {
    switch (s) {
      case 'pending':
        return Icons.hourglass_empty;
      case 'accepted':
        return Icons.check_circle_outline;
      case 'preparing':
        return Icons.inventory_2_outlined;
      case 'out_for_delivery':
        return Icons.local_shipping_outlined;
      case 'delivered':
        return Icons.task_alt;
      case 'completed':
        return Icons.verified_outlined;
      case 'cancelled':
        return Icons.cancel_outlined;
      default:
        return Icons.circle;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final semantic = context.semanticColors;
    late Color bg;
    late Color fg;
    switch (status) {
      case 'pending':
        bg = scheme.surfaceContainerHighest;
        fg = scheme.onSurfaceVariant;
        break;
      case 'accepted':
      case 'preparing':
        bg = scheme.secondaryContainer;
        fg = scheme.onSecondaryContainer;
        break;
      case 'out_for_delivery':
        bg = scheme.primary;
        fg = scheme.onPrimary;
        break;
      case 'delivered':
      case 'completed':
        bg = semantic.success;
        fg = semantic.onSuccess;
        break;
      case 'cancelled':
        bg = scheme.errorContainer;
        fg = scheme.onErrorContainer;
        break;
      default:
        bg = scheme.surfaceContainerHighest;
        fg = scheme.onSurfaceVariant;
    }
    final height = size == OrderStatusChipSize.sm ? 24.0 : 32.0;
    final iconSize = size == OrderStatusChipSize.sm ? 14.0 : 18.0;
    final text = humanLabel(status);
    return Semantics(
      label: 'Status: $text',
      child: Container(
        height: height,
        padding: const EdgeInsets.symmetric(horizontal: 10),
        decoration: BoxDecoration(
          color: bg,
          borderRadius: BorderRadius.circular(AppRadius.pill),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(iconFor(status), size: iconSize, color: fg),
            const SizedBox(width: 6),
            Text(
              text,
              style: context.textStyles.labelSmall?.copyWith(color: fg),
            ),
          ],
        ),
      ),
    );
  }
}
