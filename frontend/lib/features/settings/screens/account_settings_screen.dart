import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_list_tile.dart';

class AccountSettingsScreen extends StatelessWidget {
  const AccountSettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppTopBar(title: 'Account settings'),
      body: SafeArea(
        child: ListView(
          children: [
            AppListTile(
              leading: const Icon(Icons.person_outline),
              title: 'Edit profile',
              onTap: () => context.push(AppRoutes.editProfile),
            ),
            AppListTile(
              leading: const Icon(Icons.lock_outline),
              title: 'Change password',
              onTap: () => context.push(AppRoutes.changePassword),
            ),
            AppListTile(
              leading: const Icon(Icons.notifications_outlined),
              title: 'Notifications',
              onTap: () => context.push(AppRoutes.notificationPrefs),
              showDivider: false,
            ),
          ],
        ),
      ),
    );
  }
}
