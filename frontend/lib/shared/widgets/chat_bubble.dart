// Phase 10 widget stubbed for Phase 8. Contract: accepts ONLY decrypted
// plaintext. This widget must never expose a `ciphertext` parameter — see
// ADR-0009/0013 and frontend-spec/02-component-library.md §6.
import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

enum MessageStatus { sending, sent, read, failed }

class ChatBubble extends StatelessWidget {
  const ChatBubble({
    super.key,
    required this.text,
    required this.isMine,
    required this.sentAt,
    required this.status,
    this.onRetry,
  });

  /// Already-decrypted plaintext. Never ciphertext, never base64.
  final String text;
  final bool isMine;
  final DateTime sentAt;
  final MessageStatus status;
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final bg = isMine ? scheme.primary : scheme.surfaceContainerHighest;
    final fg = isMine ? scheme.onPrimary : scheme.onSurfaceVariant;
    final alignment = isMine ? Alignment.centerRight : Alignment.centerLeft;

    final radius = BorderRadius.only(
      topLeft: const Radius.circular(AppRadius.md),
      topRight: const Radius.circular(AppRadius.md),
      bottomLeft: Radius.circular(isMine ? AppRadius.md : 4),
      bottomRight: Radius.circular(isMine ? 4 : AppRadius.md),
    );

    return Align(
      alignment: alignment,
      child: ConstraintsFor72Percent(
        child: Opacity(
          opacity: status == MessageStatus.sending ? 0.6 : 1.0,
          child: Container(
            margin: const EdgeInsets.symmetric(vertical: AppSpacing.s1),
            padding: const EdgeInsets.symmetric(
              horizontal: AppSpacing.s4,
              vertical: AppSpacing.s3,
            ),
            decoration: BoxDecoration(color: bg, borderRadius: radius),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Text(text, style: context.textStyles.bodyMedium?.copyWith(color: fg)),
                const SizedBox(height: AppSpacing.s1),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _formatTime(sentAt),
                      style: context.textStyles.labelSmall?.copyWith(color: fg),
                    ),
                    if (isMine) ...[
                      const SizedBox(width: AppSpacing.s1),
                      _statusIcon(context, fg),
                    ],
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _statusIcon(BuildContext context, Color fg) {
    switch (status) {
      case MessageStatus.sending:
        return Icon(Icons.access_time, size: 12, color: fg);
      case MessageStatus.sent:
        return Icon(Icons.check, size: 12, color: fg);
      case MessageStatus.read:
        return Icon(Icons.done_all, size: 12, color: fg);
      case MessageStatus.failed:
        return GestureDetector(
          onTap: onRetry,
          child: Icon(Icons.error_outline, size: 12, color: context.colors.error),
        );
    }
  }

  String _formatTime(DateTime dt) {
    final local = dt.toLocal();
    final hh = local.hour.toString().padLeft(2, '0');
    final mm = local.minute.toString().padLeft(2, '0');
    return '$hh:$mm';
  }
}

class ConstraintsFor72Percent extends StatelessWidget {
  const ConstraintsFor72Percent({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) {
    return LayoutBuilder(
      builder: (ctx, constraints) => ConstrainedBox(
        constraints: BoxConstraints(maxWidth: constraints.maxWidth * 0.72),
        child: child,
      ),
    );
  }
}
