import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';
import 'app_button.dart';

class AppEmptyState extends StatelessWidget {
  const AppEmptyState({
    super.key,
    required this.icon,
    required this.headline,
    this.subhead,
    this.ctaLabel,
    this.onCtaPressed,
  });

  final IconData icon;
  final String headline;
  final String? subhead;
  final String? ctaLabel;
  final VoidCallback? onCtaPressed;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 320),
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.s5),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.center,
            children: [
              Icon(icon, size: 32, color: context.colors.onSurfaceVariant),
              const SizedBox(height: AppSpacing.s4),
              Text(
                headline,
                style: context.textStyles.headlineMedium,
                textAlign: TextAlign.center,
              ),
              if (subhead != null) ...[
                const SizedBox(height: AppSpacing.s2),
                Text(
                  subhead!,
                  style: context.textStyles.bodyMedium?.copyWith(
                    color: context.colors.onSurfaceVariant,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
              if (ctaLabel != null) ...[
                const SizedBox(height: AppSpacing.s5),
                AppButton(
                  label: ctaLabel!,
                  onPressed: onCtaPressed,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
