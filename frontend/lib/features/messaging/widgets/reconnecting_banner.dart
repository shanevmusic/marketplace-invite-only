import 'package:flutter/material.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../realtime/realtime_status.dart';

/// Thin banner surfaced on the messaging/tracking screens when the WS socket
/// is reconnecting. Reused widget — not a separate per-feature copy.
class ReconnectingBanner extends StatelessWidget {
  const ReconnectingBanner({super.key, required this.status});
  final RealtimeStatus status;

  @override
  Widget build(BuildContext context) {
    if (status != RealtimeStatus.reconnecting &&
        status != RealtimeStatus.unauthorized) {
      return const SizedBox.shrink();
    }
    final label = status == RealtimeStatus.unauthorized
        ? 'Session expired. Log in again.'
        : 'Reconnecting…';
    return Semantics(
      liveRegion: true,
      label: label,
      child: Container(
        height: 32,
        width: double.infinity,
        color: context.colors.surfaceContainerHighest,
        alignment: Alignment.center,
        padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s4),
        child: Text(
          label,
          style: context.textStyles.labelSmall?.copyWith(
            color: context.colors.onSurfaceVariant,
          ),
        ),
      ),
    );
  }
}
