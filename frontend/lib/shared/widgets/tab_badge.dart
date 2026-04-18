import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';

class TabBadge extends StatelessWidget {
  const TabBadge({
    super.key,
    required this.child,
    this.count,
    this.visible = true,
  });

  final Widget child;
  final int? count;
  final bool visible;

  @override
  Widget build(BuildContext context) {
    if (!visible) return child;
    final scheme = context.colors;
    final label = count == null ? '' : (count! > 99 ? '99+' : '$count');
    return Stack(
      clipBehavior: Clip.none,
      children: [
        child,
        Positioned(
          top: -2,
          right: -6,
          child: Container(
            constraints: const BoxConstraints(minWidth: 16, minHeight: 16),
            padding: const EdgeInsets.symmetric(horizontal: 4),
            decoration: BoxDecoration(
              color: scheme.error,
              borderRadius: BorderRadius.circular(8),
            ),
            alignment: Alignment.center,
            child: count == null
                ? const SizedBox(width: 8, height: 8)
                : Text(
                    label,
                    style: context.textStyles.labelSmall?.copyWith(
                      color: scheme.onError,
                      fontSize: 10,
                      height: 1,
                    ),
                  ),
          ),
        ),
      ],
    );
  }
}
