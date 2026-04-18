// Phase 10 extension of the Phase 8 scaffold. Contract: accepts ONLY
// decrypted plaintext. This widget must never expose a `ciphertext`
// parameter — see ADR-0009/0013 and the crypto-boundary invariant test.
import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

/// 7-state machine per frontend-spec/phase-10-messaging.md §4.1.
enum MessageStatus {
  pending,
  sending,
  sent,
  delivered,
  read,
  failed,
  decryptionError,
}

class ChatBubble extends StatelessWidget {
  const ChatBubble({
    super.key,
    required this.text,
    required this.isMine,
    required this.sentAt,
    required this.status,
    this.onRetry,
    this.onLongPress,
    this.senderDisplayName,
  });

  /// Already-decrypted plaintext. Never ciphertext, never base64.
  final String text;
  final bool isMine;
  final DateTime sentAt;
  final MessageStatus status;
  final VoidCallback? onRetry;
  final VoidCallback? onLongPress;
  final String? senderDisplayName;

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final isError = status == MessageStatus.decryptionError;
    final bg = isError
        ? scheme.surfaceContainerHighest
        : isMine
            ? scheme.primary
            : scheme.surfaceContainerHighest;
    final fg = isError
        ? scheme.onSurfaceVariant
        : isMine
            ? scheme.onPrimary
            : scheme.onSurfaceVariant;
    final alignment = isMine ? Alignment.centerRight : Alignment.centerLeft;

    final radius = BorderRadius.only(
      topLeft: const Radius.circular(AppRadius.md),
      topRight: const Radius.circular(AppRadius.md),
      bottomLeft: Radius.circular(isMine ? AppRadius.md : 4),
      bottomRight: Radius.circular(isMine ? 4 : AppRadius.md),
    );

    final opacity = switch (status) {
      MessageStatus.pending => 0.6,
      MessageStatus.sending => 0.7,
      MessageStatus.decryptionError => 0.8,
      _ => 1.0,
    };

    final decoration = BoxDecoration(
      color: bg,
      borderRadius: radius,
      border: status == MessageStatus.failed
          ? Border(left: BorderSide(color: scheme.error, width: 2))
          : null,
    );

    final body = Opacity(
      opacity: opacity,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: AppSpacing.s1),
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s4,
          vertical: AppSpacing.s3,
        ),
        decoration: decoration,
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            Text(
              isError ? "🔒 Couldn't decrypt this message" : text,
              style:
                  (context.textStyles.bodyMedium ?? const TextStyle()).copyWith(
                color: fg,
                fontStyle: isError ? FontStyle.italic : FontStyle.normal,
              ),
            ),
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
    );

    final captioned = status == MessageStatus.pending
        ? Column(
            crossAxisAlignment:
                isMine ? CrossAxisAlignment.end : CrossAxisAlignment.start,
            children: [
              body,
              Padding(
                padding: const EdgeInsets.only(top: 2),
                child: Text(
                  'Will send when online',
                  style: context.textStyles.labelSmall
                      ?.copyWith(fontStyle: FontStyle.italic),
                ),
              ),
            ],
          )
        : body;

    final tappable = GestureDetector(
      onTap: status == MessageStatus.failed ? onRetry : null,
      onLongPress: onLongPress,
      child: captioned,
    );

    return Semantics(
      label: _semanticsLabel(),
      child: Align(
        alignment: alignment,
        child: ConstraintsFor72Percent(child: tappable),
      ),
    );
  }

  Widget _statusIcon(BuildContext context, Color fg) {
    switch (status) {
      case MessageStatus.pending:
        return Icon(Icons.schedule, size: 12, color: fg.withValues(alpha: 0.6));
      case MessageStatus.sending:
        return Icon(Icons.access_time, size: 12, color: fg);
      case MessageStatus.sent:
        return Icon(Icons.check, size: 12, color: fg);
      case MessageStatus.delivered:
        return Icon(Icons.done_all, size: 12, color: fg.withValues(alpha: 0.6));
      case MessageStatus.read:
        return Icon(Icons.done_all, size: 12, color: context.colors.tertiary);
      case MessageStatus.failed:
        return Icon(Icons.error_outline, size: 12, color: context.colors.error);
      case MessageStatus.decryptionError:
        return Icon(Icons.lock_outline, size: 12, color: fg);
    }
  }

  String _semanticsLabel() {
    final who = isMine ? 'You said' : '${senderDisplayName ?? 'Peer'} said';
    final statusLabel = switch (status) {
      MessageStatus.pending => ' Pending — will send when online.',
      MessageStatus.sending => ' Sending.',
      MessageStatus.sent => ' Sent.',
      MessageStatus.delivered => ' Delivered.',
      MessageStatus.read => ' Read.',
      MessageStatus.failed => ' Failed. Double-tap to retry.',
      MessageStatus.decryptionError => ' Could not be decrypted.',
    };
    final body = status == MessageStatus.decryptionError
        ? "Couldn't decrypt this message"
        : text;
    return '$who: $body. Sent ${_formatTime(sentAt)}.$statusLabel';
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
