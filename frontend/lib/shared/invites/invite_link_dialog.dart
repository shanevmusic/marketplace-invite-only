import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';
import '../widgets/app_button.dart';
import '../widgets/app_snackbar.dart';
import 'invite_link.dart';

/// Bottom sheet that displays a shareable invite link for a token.
///
/// - Shows the role/audience (optional [roleTarget]).
/// - Renders the public URL as a selectable, copyable block.
/// - Provides a single "Copy link" button (copy-only per product spec).
/// - Falls back to the marketplace:// deep-link if no public base URL was
///   compiled in via --dart-define=INVITE_BASE_URL.
class InviteLinkSheet extends StatelessWidget {
  const InviteLinkSheet({
    super.key,
    required this.token,
    this.title = 'Invite link',
    this.roleTarget,
    this.subtitle,
    this.onRegenerate,
  });

  final String token;
  final String title;
  final String? roleTarget;
  final String? subtitle;
  final VoidCallback? onRegenerate;

  static Future<void> show(
    BuildContext context, {
    required String token,
    String title = 'Invite link',
    String? roleTarget,
    String? subtitle,
    VoidCallback? onRegenerate,
  }) {
    return showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      showDragHandle: true,
      builder: (_) => Padding(
        padding: EdgeInsets.only(
          bottom: MediaQuery.of(context).viewInsets.bottom,
        ),
        child: InviteLinkSheet(
          token: token,
          title: title,
          roleTarget: roleTarget,
          subtitle: subtitle,
          onRegenerate: onRegenerate,
        ),
      ),
    );
  }

  String get _url => InviteLink.forToken(token);

  Future<void> _copy(BuildContext context) async {
    await Clipboard.setData(ClipboardData(text: _url));
    if (!context.mounted) return;
    context.showAppSnackbar(message: 'Link copied');
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final textStyles = context.textStyles;
    final caption = subtitle ??
        (roleTarget != null
            ? 'Anyone with this link can sign up as a $roleTarget.'
            : 'Anyone with this link can sign up.');

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.fromLTRB(
          AppSpacing.s5,
          AppSpacing.s2,
          AppSpacing.s5,
          AppSpacing.s5,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: textStyles.titleLarge),
            const SizedBox(height: AppSpacing.s2),
            Text(
              caption,
              style: textStyles.bodyMedium?.copyWith(
                color: colors.onSurfaceVariant,
              ),
            ),
            const SizedBox(height: AppSpacing.s4),
            Container(
              padding: const EdgeInsets.all(AppSpacing.s3),
              decoration: BoxDecoration(
                color: colors.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(AppRadius.sm),
                border: Border.all(color: colors.outlineVariant),
              ),
              child: SelectableText(
                _url,
                style: textStyles.bodyMedium?.copyWith(
                  fontFamily: 'monospace',
                ),
                maxLines: 4,
              ),
            ),
            if (!InviteLink.hasPublicBase) ...[
              const SizedBox(height: AppSpacing.s2),
              Text(
                'Tip: this is a deep link — recipient needs the app installed.',
                style: textStyles.bodySmall?.copyWith(
                  color: colors.onSurfaceVariant,
                ),
              ),
            ],
            const SizedBox(height: AppSpacing.s4),
            AppButton(
              label: 'Copy link',
              leadingIcon: Icons.copy,
              size: AppButtonSize.lg,
              expand: true,
              onPressed: () => _copy(context),
            ),
            if (onRegenerate != null) ...[
              const SizedBox(height: AppSpacing.s2),
              AppButton(
                label: 'Generate new link',
                leadingIcon: Icons.refresh,
                variant: AppButtonVariant.text,
                expand: true,
                onPressed: () {
                  Navigator.of(context).pop();
                  onRegenerate!();
                },
              ),
            ],
          ],
        ),
      ),
    );
  }
}
