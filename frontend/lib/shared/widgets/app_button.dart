import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

enum AppButtonVariant { primary, secondary, text, destructive }

enum AppButtonSize { sm, md, lg }

/// Token-driven button — variant + size → ButtonStyle. Handles loading state
/// by hiding the label and showing a centered CircularProgressIndicator.
class AppButton extends StatelessWidget {
  const AppButton({
    super.key,
    required this.label,
    this.onPressed,
    this.variant = AppButtonVariant.primary,
    this.size = AppButtonSize.md,
    this.leadingIcon,
    this.trailingIcon,
    this.isLoading = false,
    this.expand = false,
    this.semanticsLabel,
  });

  final String label;
  final VoidCallback? onPressed;
  final AppButtonVariant variant;
  final AppButtonSize size;
  final IconData? leadingIcon;
  final IconData? trailingIcon;
  final bool isLoading;
  final bool expand;
  final String? semanticsLabel;

  double get _height {
    switch (size) {
      case AppButtonSize.sm:
        return 36;
      case AppButtonSize.md:
        return 48;
      case AppButtonSize.lg:
        return 56;
    }
  }

  double get _hPad {
    switch (size) {
      case AppButtonSize.sm:
        return 12;
      case AppButtonSize.md:
        return 16;
      case AppButtonSize.lg:
        return 24;
    }
  }

  TextStyle? _labelStyle(BuildContext context) {
    switch (size) {
      case AppButtonSize.sm:
        return context.textStyles.labelMedium;
      case AppButtonSize.md:
        return context.textStyles.labelLarge;
      case AppButtonSize.lg:
        return context.textStyles.titleMedium;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final disabled = onPressed == null || isLoading;

    final (bg, fg) = _palette(scheme, context);

    final child = isLoading
        ? SizedBox(
            width: 20,
            height: 20,
            child: CircularProgressIndicator(
              strokeWidth: 2,
              valueColor: AlwaysStoppedAnimation<Color>(fg),
            ),
          )
        : Row(
            mainAxisSize: MainAxisSize.min,
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              if (leadingIcon != null) ...[
                Icon(leadingIcon, size: 20, color: fg),
                const SizedBox(width: AppSpacing.s2),
              ],
              Flexible(
                child: Text(
                  label,
                  style: _labelStyle(context)?.copyWith(color: fg),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              if (trailingIcon != null) ...[
                const SizedBox(width: AppSpacing.s2),
                Icon(trailingIcon, size: 20, color: fg),
              ],
            ],
          );

    final button = Material(
      color: bg,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.sm),
        side: variant == AppButtonVariant.text
            ? BorderSide.none
            : BorderSide.none,
      ),
      child: InkWell(
        onTap: disabled ? null : onPressed,
        borderRadius: BorderRadius.circular(AppRadius.sm),
        child: Container(
          height: _height,
          padding: EdgeInsets.symmetric(horizontal: _hPad),
          alignment: Alignment.center,
          constraints: BoxConstraints(minHeight: 44, minWidth: 44),
          child: child,
        ),
      ),
    );

    final sized = expand ? SizedBox(width: double.infinity, child: button) : button;

    return Semantics(
      button: true,
      enabled: !disabled,
      label: semanticsLabel ?? label,
      child: Opacity(opacity: disabled && !isLoading ? 0.38 : 1.0, child: sized),
    );
  }

  (Color, Color) _palette(ColorScheme scheme, BuildContext context) {
    switch (variant) {
      case AppButtonVariant.primary:
        return (scheme.primary, scheme.onPrimary);
      case AppButtonVariant.secondary:
        return (scheme.surfaceContainerHighest, scheme.onSurfaceVariant);
      case AppButtonVariant.text:
        return (Colors.transparent, scheme.primary);
      case AppButtonVariant.destructive:
        return (scheme.error, scheme.onError);
    }
  }
}
