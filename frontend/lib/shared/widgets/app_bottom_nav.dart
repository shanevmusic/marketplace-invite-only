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
    return NavigationBar(
      selectedIndex: currentIndex,
      onDestinationSelected: onTap,
      backgroundColor: scheme.surface,
      indicatorColor: scheme.primaryContainer,
      height: 64,
      destinations: [
        for (final it in items)
          NavigationDestination(
            icon: Icon(it.icon, color: scheme.onSurfaceVariant),
            selectedIcon: Icon(it.activeIcon, color: scheme.primary),
            label: it.label,
            tooltip: it.semanticsLabel ?? it.label,
          ),
      ],
    );
  }
}
