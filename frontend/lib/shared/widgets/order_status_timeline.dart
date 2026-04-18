import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';
import 'order_status_chip.dart';

class OrderStatusTimeline extends StatelessWidget {
  const OrderStatusTimeline({
    super.key,
    required this.currentStatus,
    required this.placedAt,
    this.acceptedAt,
    this.preparingAt,
    this.outForDeliveryAt,
    this.deliveredAt,
    this.completedAt,
    this.cancelledAt,
  });

  final String currentStatus;
  final DateTime placedAt;
  final DateTime? acceptedAt;
  final DateTime? preparingAt;
  final DateTime? outForDeliveryAt;
  final DateTime? deliveredAt;
  final DateTime? completedAt;
  final DateTime? cancelledAt;

  @override
  Widget build(BuildContext context) {
    final steps = <_Step>[
      _Step('Placed', placedAt),
      _Step('Accepted', acceptedAt),
      _Step('Preparing', preparingAt),
      _Step('Out for delivery', outForDeliveryAt),
      _Step('Delivered', deliveredAt),
      _Step('Completed', completedAt),
    ];
    if (currentStatus == 'cancelled') {
      final filled = steps.takeWhile((s) => s.at != null).toList();
      filled.add(_Step('Cancelled', cancelledAt, cancelled: true));
      return Semantics(
        label:
            'Order status: ${OrderStatusChip.humanLabel(currentStatus)}',
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (int i = 0; i < filled.length; i++)
              _StepRow(
                step: filled[i],
                isLast: i == filled.length - 1,
                isCurrent: i == filled.length - 1,
              ),
          ],
        ),
      );
    }
    return Semantics(
      label: 'Order status: ${OrderStatusChip.humanLabel(currentStatus)}',
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          for (int i = 0; i < steps.length; i++)
            _StepRow(
              step: steps[i],
              isLast: i == steps.length - 1,
              isCurrent: _statusIndex(currentStatus) == i,
            ),
        ],
      ),
    );
  }

  int _statusIndex(String s) {
    switch (s) {
      case 'pending':
        return 0;
      case 'accepted':
        return 1;
      case 'preparing':
        return 2;
      case 'out_for_delivery':
        return 3;
      case 'delivered':
        return 4;
      case 'completed':
        return 5;
      default:
        return 0;
    }
  }
}

class _Step {
  _Step(this.label, this.at, {this.cancelled = false});
  final String label;
  final DateTime? at;
  final bool cancelled;
}

class _StepRow extends StatelessWidget {
  const _StepRow({
    required this.step,
    required this.isLast,
    required this.isCurrent,
  });

  final _Step step;
  final bool isLast;
  final bool isCurrent;

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final filled = step.at != null;
    final dotColor = step.cancelled
        ? scheme.error
        : filled
            ? scheme.primary
            : scheme.outlineVariant;
    return IntrinsicHeight(
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Column(
            children: [
              Container(
                width: 14,
                height: 14,
                margin: const EdgeInsets.symmetric(vertical: 6),
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: filled || step.cancelled
                      ? dotColor
                      : Colors.transparent,
                  border: Border.all(color: dotColor, width: 2),
                ),
              ),
              if (!isLast)
                Expanded(
                  child: Container(
                    width: 2,
                    color: filled ? scheme.outline : scheme.outlineVariant,
                  ),
                ),
            ],
          ),
          const SizedBox(width: AppSpacing.s3),
          Expanded(
            child: Padding(
              padding: const EdgeInsets.only(bottom: AppSpacing.s3),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    step.label,
                    style: context.textStyles.titleSmall?.copyWith(
                      color: filled
                          ? scheme.onSurface
                          : scheme.onSurfaceVariant,
                      fontWeight: isCurrent ? FontWeight.w700 : null,
                    ),
                  ),
                  if (step.at != null)
                    Text(
                      DateFormat('MMM d, h:mm a').format(step.at!.toLocal()),
                      style: context.textStyles.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    )
                  else
                    Text(
                      'Not yet',
                      style: context.textStyles.bodySmall?.copyWith(
                        color: scheme.onSurfaceVariant,
                      ),
                    ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
