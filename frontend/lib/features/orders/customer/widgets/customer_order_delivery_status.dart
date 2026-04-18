// ADR-0014: asymmetric delivery visibility — the customer side NEVER sees
// coordinates, driver identity, seller geo, breadcrumbs, distances, or ETAs
// beyond the opaque string the server renders. Do not add lat/lng/driver_id
// fields here. See frontend-spec/phase-9-customer-flows.md §order-detail.
import 'package:flutter/material.dart';

import '../../../../app/theme/theme_extensions.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../../../shared/widgets/order_status_chip.dart';
import '../../data/order_dtos.dart';

/// Props exposed to the customer order-detail screen. Intentionally missing
/// coordinate and driver-identity fields.
class CustomerOrderDeliveryProps {
  const CustomerOrderDeliveryProps({
    required this.orderId,
    required this.status,
    required this.deliveryAddress,
    this.etaText,
    this.startedAt,
    this.deliveredAt,
  });

  final String orderId;
  final String status;
  final DeliveryAddress deliveryAddress;
  final String? etaText;
  final DateTime? startedAt;
  final DateTime? deliveredAt;

  static CustomerOrderDeliveryProps fromOrder(OrderResponse o) =>
      CustomerOrderDeliveryProps(
        orderId: o.id,
        status: o.status,
        deliveryAddress: o.deliveryAddress,
      );
}

class CustomerDeliveryStatusWidget extends StatelessWidget {
  const CustomerDeliveryStatusWidget({super.key, required this.props});
  final CustomerOrderDeliveryProps props;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              OrderStatusChip(status: props.status),
              const Spacer(),
              if (props.etaText != null)
                Text(
                  props.etaText!,
                  style: context.textStyles.bodyMedium,
                ),
            ],
          ),
          const SizedBox(height: AppSpacing.s3),
          Text(
            'Delivering to',
            style: context.textStyles.labelMedium?.copyWith(
              color: context.colors.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: AppSpacing.s1),
          Text(
            props.deliveryAddress.oneLine(),
            style: context.textStyles.bodyMedium,
          ),
          const SizedBox(height: AppSpacing.s3),
          Container(
            padding: const EdgeInsets.all(AppSpacing.s3),
            decoration: BoxDecoration(
              color: context.colors.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(AppRadius.sm),
            ),
            child: Row(
              children: [
                Icon(
                  Icons.lock_outline,
                  size: 16,
                  color: context.colors.onSurfaceVariant,
                ),
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
        ],
      ),
    );
  }
}
