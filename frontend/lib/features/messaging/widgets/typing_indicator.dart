import 'package:flutter/material.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';

class TypingIndicator extends StatelessWidget {
  const TypingIndicator({super.key, required this.peerDisplayName});

  final String peerDisplayName;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      liveRegion: true,
      label: '$peerDisplayName is typing',
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s4,
          vertical: AppSpacing.s2,
        ),
        child: Align(
          alignment: Alignment.centerLeft,
          child: Container(
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.s3,
              vertical: AppSpacing.s2,
            ),
            decoration: BoxDecoration(
              color: context.colors.surfaceContainerHighest,
              borderRadius: BorderRadius.circular(AppRadius.md),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                for (int i = 0; i < 3; i++) ...[
                  _Dot(delayMs: i * 200),
                  if (i < 2) const SizedBox(width: 2),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _Dot extends StatelessWidget {
  const _Dot({required this.delayMs});
  final int delayMs;

  @override
  Widget build(BuildContext context) {
    return Icon(
      Icons.circle,
      size: 6,
      color: context.colors.onSurfaceVariant.withValues(alpha: 0.6),
    );
  }
}
