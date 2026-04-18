import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';
import 'app_button.dart';

class AppDialogAction {
  const AppDialogAction({
    required this.label,
    required this.onPressed,
    this.destructive = false,
  });
  final String label;
  final VoidCallback onPressed;
  final bool destructive;
}

class AppDialog extends StatelessWidget {
  const AppDialog({
    super.key,
    required this.title,
    required this.body,
    required this.primaryAction,
    this.secondaryAction,
  });

  final String title;
  final Widget body;
  final AppDialogAction primaryAction;
  final AppDialogAction? secondaryAction;

  static Future<void> show(
    BuildContext context, {
    required String title,
    required Widget body,
    required AppDialogAction primaryAction,
    AppDialogAction? secondaryAction,
    bool dismissible = true,
  }) =>
      showDialog<void>(
        context: context,
        barrierDismissible: dismissible,
        builder: (_) => AppDialog(
          title: title,
          body: body,
          primaryAction: primaryAction,
          secondaryAction: secondaryAction,
        ),
      );

  @override
  Widget build(BuildContext context) {
    return Dialog(
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(AppRadius.md),
      ),
      child: Padding(
        padding: const EdgeInsets.all(AppSpacing.s5),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(title, style: context.textStyles.titleLarge),
            const SizedBox(height: AppSpacing.s3),
            body,
            const SizedBox(height: AppSpacing.s5),
            Row(
              mainAxisAlignment: MainAxisAlignment.end,
              children: [
                if (secondaryAction != null) ...[
                  AppButton(
                    label: secondaryAction!.label,
                    variant: AppButtonVariant.text,
                    onPressed: secondaryAction!.onPressed,
                  ),
                  const SizedBox(width: AppSpacing.s2),
                ],
                AppButton(
                  label: primaryAction.label,
                  variant: primaryAction.destructive
                      ? AppButtonVariant.destructive
                      : AppButtonVariant.primary,
                  onPressed: primaryAction.onPressed,
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
