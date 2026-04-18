import 'package:flutter/material.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';

class SafetyNumberView extends StatelessWidget {
  const SafetyNumberView({super.key, required this.safetyNumber});
  final String safetyNumber;

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Text(
          'Safety number',
          style: context.textStyles.bodyMedium?.copyWith(
            color: context.colors.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: AppSpacing.s2),
        Text(
          safetyNumber,
          style: (context.textStyles.titleLarge ?? const TextStyle()).copyWith(
            fontFamily: 'monospace',
          ),
        ),
      ],
    );
  }
}
