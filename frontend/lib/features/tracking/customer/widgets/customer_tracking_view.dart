// ADR-0014: this file is under lib/features/tracking/customer/. It must not
// reference coordinate fields or any map SDK. Props are strictly status,
// ETA, timeline timestamps, and a human-formatted destination label. Any
// edit adding a coord field here is a type-system change — reject on review.
import 'package:flutter/material.dart';

import '../../../../app/theme/theme_extensions.dart';
import '../../../../app/theme/tokens.dart';
import '../../../../shared/widgets/app_card.dart';
import '../../shared/delivery_status.dart';

class CustomerTrackingProps {
  const CustomerTrackingProps({
    required this.orderId,
    required this.status,
    required this.destinationLabel,
    this.etaSeconds,
    this.etaUpdatedAt,
    this.lastUpdatedAt,
    this.sellerDisplayName,
  });

  final String orderId;
  final TrackingDeliveryStatus status;
  final int? etaSeconds;
  final DateTime? etaUpdatedAt;
  final DateTime? lastUpdatedAt;
  final String destinationLabel;
  final String? sellerDisplayName;
}

class CustomerTrackingView extends StatelessWidget {
  const CustomerTrackingView({super.key, required this.props});
  final CustomerTrackingProps props;

  @override
  Widget build(BuildContext context) {
    final headline = statusHeadline(props.status);
    return ListView(
      padding: const EdgeInsets.all(AppSpacing.s4),
      children: [
        AppCard(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.s4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(_statusIcon(),
                        size: 40, color: context.colors.primary),
                    const SizedBox(width: AppSpacing.s3),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(headline, style: context.textStyles.titleLarge),
                          const SizedBox(height: AppSpacing.s1),
                          Text(
                            _subhead(),
                            style: context.textStyles.bodyMedium?.copyWith(
                              color: context.colors.onSurfaceVariant,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
                if (props.status == TrackingDeliveryStatus.outForDelivery) ...[
                  const SizedBox(height: AppSpacing.s3),
                  Container(
                    padding: const EdgeInsets.symmetric(
                      horizontal: AppSpacing.s4,
                      vertical: AppSpacing.s2,
                    ),
                    decoration: BoxDecoration(
                      color: context.colors.tertiaryContainer,
                      borderRadius: BorderRadius.circular(AppRadius.md),
                    ),
                    child: Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.schedule,
                            size: 16,
                            color: context.colors.onTertiaryContainer),
                        const SizedBox(width: AppSpacing.s2),
                        Text(
                          etaCopy(props.etaSeconds),
                          style: context.textStyles.titleMedium?.copyWith(
                            color: context.colors.onTertiaryContainer,
                          ),
                        ),
                      ],
                    ),
                  ),
                ],
                if (props.lastUpdatedAt != null) ...[
                  const SizedBox(height: AppSpacing.s2),
                  Text(
                    'Last updated ${_relative(props.lastUpdatedAt!)}',
                    style: context.textStyles.labelSmall?.copyWith(
                      color: context.colors.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: AppSpacing.s4),
        AppCard(
          child: Padding(
            padding: const EdgeInsets.all(AppSpacing.s4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    const Icon(Icons.place_outlined, size: 18),
                    const SizedBox(width: AppSpacing.s2),
                    Text('Delivery address',
                        style: context.textStyles.labelLarge),
                  ],
                ),
                const SizedBox(height: AppSpacing.s2),
                Text(props.destinationLabel,
                    style: context.textStyles.bodyMedium),
              ],
            ),
          ),
        ),
      ],
    );
  }

  IconData _statusIcon() {
    switch (props.status) {
      case TrackingDeliveryStatus.pending:
        return Icons.receipt_long_outlined;
      case TrackingDeliveryStatus.accepted:
        return Icons.check_circle_outline;
      case TrackingDeliveryStatus.preparing:
        return Icons.inventory_2_outlined;
      case TrackingDeliveryStatus.outForDelivery:
        return Icons.local_shipping_outlined;
      case TrackingDeliveryStatus.delivered:
        return Icons.task_alt;
      case TrackingDeliveryStatus.completed:
        return Icons.verified_outlined;
      case TrackingDeliveryStatus.cancelled:
        return Icons.cancel_outlined;
    }
  }

  String _subhead() {
    switch (props.status) {
      case TrackingDeliveryStatus.pending:
        return 'Your order is placed and waiting for the seller to accept.';
      case TrackingDeliveryStatus.accepted:
        return 'The seller will start preparing soon.';
      case TrackingDeliveryStatus.preparing:
        return 'The seller is getting your order ready.';
      case TrackingDeliveryStatus.outForDelivery:
        return 'Your order is on the way.';
      case TrackingDeliveryStatus.delivered:
        return 'Your order was delivered.';
      case TrackingDeliveryStatus.completed:
        return 'Thanks for confirming receipt.';
      case TrackingDeliveryStatus.cancelled:
        return 'This order was cancelled.';
    }
  }

  String _relative(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inSeconds < 60) return 'just now';
    if (diff.inMinutes < 60) return '${diff.inMinutes} min ago';
    if (diff.inHours < 24) return '${diff.inHours} h ago';
    return '${diff.inDays} d ago';
  }
}
