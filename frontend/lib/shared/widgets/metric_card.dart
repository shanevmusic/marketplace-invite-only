import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';
import 'app_card.dart';

class MetricCard extends StatelessWidget {
  const MetricCard({
    super.key,
    required this.label,
    required this.value,
    this.caption,
    this.onTap,
    this.trailing,
  });

  final String label;
  final String value;
  final String? caption;
  final VoidCallback? onTap;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      variant: onTap != null ? AppCardVariant.interactive : AppCardVariant.standard,
      onTap: onTap,
      semanticsLabel: onTap != null
          ? '$label, $value${caption != null ? ', ${caption!}' : ''}'
          : null,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: context.textStyles.labelMedium?.copyWith(
                    color: context.colors.onSurfaceVariant,
                  ),
                ),
                const SizedBox(height: AppSpacing.s1),
                Text(
                  value,
                  style: context.textStyles.headlineSmall,
                ),
                if (caption != null) ...[
                  const SizedBox(height: AppSpacing.s1),
                  Text(
                    caption!,
                    style: context.textStyles.bodySmall?.copyWith(
                      color: context.colors.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (trailing != null) trailing!,
        ],
      ),
    );
  }
}
