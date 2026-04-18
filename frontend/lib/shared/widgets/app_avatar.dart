import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import 'role_badge.dart';

enum AvatarSize { sm, md, lg }

class AppAvatar extends StatelessWidget {
  const AppAvatar({
    super.key,
    required this.initials,
    this.imageUrl,
    this.size = AvatarSize.md,
    this.role,
  });

  final String initials;
  final String? imageUrl;
  final AvatarSize size;
  final String? role;

  double get _dim {
    switch (size) {
      case AvatarSize.sm:
        return 32;
      case AvatarSize.md:
        return 40;
      case AvatarSize.lg:
        return 64;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final avatar = CircleAvatar(
      radius: _dim / 2,
      backgroundColor: scheme.primaryContainer,
      foregroundImage: imageUrl != null ? NetworkImage(imageUrl!) : null,
      child: imageUrl == null
          ? Text(
              initials,
              style: context.textStyles.labelLarge
                  ?.copyWith(color: scheme.onPrimaryContainer),
            )
          : null,
    );
    if (role == null) return avatar;
    return Stack(
      clipBehavior: Clip.none,
      children: [
        avatar,
        Positioned(
          bottom: -4,
          right: -4,
          child: RoleBadge(role: role!),
        ),
      ],
    );
  }
}
