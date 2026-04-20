import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';

class AppBottomNavItem {
  const AppBottomNavItem({
    required this.icon,
    required this.activeIcon,
    required this.label,
    this.semanticsLabel,
  });

  final IconData icon;
  final IconData activeIcon;
  final String label;
  final String? semanticsLabel;
}

/// A static, zero-animation bottom navigation bar.
///
/// Swapped from Material 3's [NavigationBar] because its default pill/indicator
/// slide animation (~500ms) felt sluggish on tab switches. This version changes
/// the selected tab instantly with no transition.
class AppBottomNav extends StatelessWidget {
  const AppBottomNav({
    super.key,
    required this.currentIndex,
    required this.items,
    required this.onTap,
  });

  final int currentIndex;
  final List<AppBottomNavItem> items;
  final ValueChanged<int> onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    return Material(
      color: scheme.surface,
      elevation: 0,
      child: SafeArea(
        top: false,
        child: SizedBox(
          height: 64,
          child: Row(
            children: [
              for (int i = 0; i < items.length; i++)
                Expanded(
                  child: _NavItem(
                    item: items[i],
                    selected: i == currentIndex,
                    onTap: () => onTap(i),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _NavItem extends StatelessWidget {
  const _NavItem({
    required this.item,
    required this.selected,
    required this.onTap,
  });

  final AppBottomNavItem item;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = context.colors;
    final color = selected ? scheme.primary : scheme.onSurfaceVariant;
    return Semantics(
      button: true,
      selected: selected,
      label: item.semanticsLabel ?? item.label,
      child: InkWell(
        onTap: onTap,
        splashColor: scheme.primaryContainer.withValues(alpha: 0.4),
        highlightColor: Colors.transparent,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              selected ? item.activeIcon : item.icon,
              color: color,
              size: 24,
            ),
            const SizedBox(height: 4),
            Text(
              item.label,
              style: TextStyle(
                color: color,
                fontSize: 12,
                fontWeight: selected ? FontWeight.w600 : FontWeight.w500,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
