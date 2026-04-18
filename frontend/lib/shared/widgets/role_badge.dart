import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

enum BadgeSize { sm, md }

class RoleBadge extends StatelessWidget {
  const RoleBadge({super.key, required this.role, this.size = BadgeSize.sm});

  final String role;
  final BadgeSize size;

  @override
  Widget build(BuildContext context) {
    final colors = context.roleBadgeColors.forRole(role);
    final bg = colors.$1;
    final fg = colors.$2;
    final vPad = size == BadgeSize.sm ? 2.0 : 4.0;
    final hPad = size == BadgeSize.sm ? AppSpacing.s2 : AppSpacing.s3;
    return Container(
      padding: EdgeInsets.symmetric(horizontal: hPad, vertical: vPad),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Text(
        role.toUpperCase(),
        style: context.textStyles.labelSmall?.copyWith(color: fg),
      ),
    );
  }
}
