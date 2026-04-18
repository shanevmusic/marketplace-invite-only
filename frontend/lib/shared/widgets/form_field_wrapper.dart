import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

/// Vertical label/field/helper stack used to unify form field spacing.
class AppFormField extends StatelessWidget {
  const AppFormField({
    super.key,
    required this.label,
    required this.child,
    this.required = false,
    this.helperText,
    this.errorText,
  });

  final String label;
  final bool required;
  final String? helperText;
  final String? errorText;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    final err = errorText;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        RichText(
          text: TextSpan(
            style: context.textStyles.labelMedium,
            children: [
              TextSpan(text: label),
              if (required)
                TextSpan(
                  text: ' *',
                  style: TextStyle(color: context.colors.error),
                ),
            ],
          ),
        ),
        const SizedBox(height: AppSpacing.s1),
        child,
        if (err != null || helperText != null) ...[
          const SizedBox(height: AppSpacing.s1),
          Semantics(
            liveRegion: err != null,
            child: Text(
              err ?? helperText!,
              style: context.textStyles.bodySmall?.copyWith(
                color: err != null ? context.colors.error : null,
              ),
            ),
          ),
        ],
      ],
    );
  }
}
