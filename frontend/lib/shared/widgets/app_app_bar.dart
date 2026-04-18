import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';

class AppTopBar extends StatelessWidget implements PreferredSizeWidget {
  const AppTopBar({
    super.key,
    required this.title,
    this.leading,
    this.trailing = const [],
    this.onBack,
  }) : assert(trailing.length <= 2, 'Max 2 trailing widgets');

  final String title;
  final Widget? leading;
  final List<Widget> trailing;
  final VoidCallback? onBack;

  @override
  Size get preferredSize => const Size.fromHeight(kToolbarHeight);

  @override
  Widget build(BuildContext context) {
    return AppBar(
      title: Text(title, style: context.textStyles.titleLarge),
      leading: leading ??
          (Navigator.canPop(context)
              ? IconButton(
                  icon: const Icon(Icons.arrow_back),
                  onPressed: onBack ?? () => Navigator.maybePop(context),
                  tooltip: 'Back',
                )
              : null),
      actions: trailing,
    );
  }
}
