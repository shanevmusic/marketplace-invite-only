import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';

enum AppSnackbarVariant { info, success, error }

extension AppSnackbarX on BuildContext {
  void showAppSnackbar({
    required String message,
    AppSnackbarVariant variant = AppSnackbarVariant.info,
    String? actionLabel,
    VoidCallback? onAction,
    Duration duration = const Duration(seconds: 4),
  }) {
    final messenger = ScaffoldMessenger.maybeOf(this);
    if (messenger == null) return;

    final scheme = colors;
    final semantic = semanticColors;
    late Color bg;
    late Color fg;
    late IconData icon;
    switch (variant) {
      case AppSnackbarVariant.info:
        bg = scheme.inverseSurface;
        fg = scheme.onInverseSurface;
        icon = Icons.info_outline;
        break;
      case AppSnackbarVariant.success:
        bg = semantic.success;
        fg = semantic.onSuccess;
        icon = Icons.check_circle;
        break;
      case AppSnackbarVariant.error:
        bg = scheme.error;
        fg = scheme.onError;
        icon = Icons.error_outline;
        break;
    }

    messenger.hideCurrentSnackBar();
    messenger.showSnackBar(
      SnackBar(
        backgroundColor: bg,
        duration: duration,
        content: Row(
          children: [
            Icon(icon, color: fg),
            const SizedBox(width: 12),
            Expanded(
              child: Text(message, style: TextStyle(color: fg)),
            ),
          ],
        ),
        action: actionLabel != null
            ? SnackBarAction(
                label: actionLabel,
                textColor: fg,
                onPressed: onAction ?? () {},
              )
            : null,
      ),
    );
  }
}
