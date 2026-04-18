import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

enum AppCardVariant { standard, interactive, selected }

class AppCard extends StatelessWidget {
  const AppCard({
    super.key,
    required this.child,
    this.variant = AppCardVariant.standard,
    this.onTap,
    this.padding,
    this.semanticsLabel,
  });

  final Widget child;
  final AppCardVariant variant;
  final VoidCallback? onTap;
  final EdgeInsets? padding;
  final String? semanticsLabel;

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final bg = variant == AppCardVariant.selected
        ? scheme.primaryContainer.withValues(alpha: 0.4)
        : scheme.surface;
    final border = variant == AppCardVariant.selected
        ? BorderSide(color: scheme.primary, width: 2)
        : BorderSide(color: scheme.outlineVariant);
    final content = Padding(
      padding: padding ?? const EdgeInsets.all(AppSpacing.s4),
      child: child,
    );
    final shape = RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(AppRadius.md),
      side: border,
    );
    final mat = Material(
      color: bg,
      elevation: AppElevation.e1,
      shape: shape,
      child: variant == AppCardVariant.interactive || onTap != null
          ? InkWell(
              onTap: onTap,
              borderRadius: BorderRadius.circular(AppRadius.md),
              child: content,
            )
          : content,
    );
    if (semanticsLabel != null) {
      return Semantics(
          label: semanticsLabel, button: onTap != null, child: mat);
    }
    return mat;
  }
}
