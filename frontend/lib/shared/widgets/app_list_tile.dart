import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

class AppListTile extends StatelessWidget {
  const AppListTile({
    super.key,
    required this.title,
    this.subtitle,
    this.leading,
    this.trailing,
    this.onTap,
    this.showDivider = true,
    this.dense = false,
    this.semanticsLabel,
  });

  final String title;
  final String? subtitle;
  final Widget? leading;
  final Widget? trailing;
  final VoidCallback? onTap;
  final bool showDivider;
  final bool dense;
  final String? semanticsLabel;

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final vPad = dense ? AppSpacing.s2 : AppSpacing.s3;
    final row = Padding(
      padding: EdgeInsets.symmetric(horizontal: AppSpacing.s4, vertical: vPad),
      child: Row(
        children: [
          if (leading != null) ...[
            SizedBox(width: 40, height: 40, child: Center(child: leading)),
            const SizedBox(width: AppSpacing.s3),
          ],
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: context.textStyles.titleMedium),
                if (subtitle != null) ...[
                  const SizedBox(height: AppSpacing.s1),
                  Text(
                    subtitle!,
                    style: context.textStyles.bodyMedium?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ],
              ],
            ),
          ),
          if (trailing != null) ...[
            const SizedBox(width: AppSpacing.s3),
            trailing!,
          ] else if (onTap != null) ...[
            const SizedBox(width: AppSpacing.s3),
            Icon(Icons.chevron_right, color: scheme.onSurfaceVariant),
          ],
        ],
      ),
    );

    final content = onTap != null
        ? InkWell(onTap: onTap, child: row)
        : row;

    final semantic = Semantics(
      button: onTap != null,
      label: semanticsLabel ?? title,
      child: content,
    );

    if (!showDivider) return semantic;
    return Column(
      children: [
        semantic,
        Divider(height: 1, color: scheme.outlineVariant),
      ],
    );
  }
}
