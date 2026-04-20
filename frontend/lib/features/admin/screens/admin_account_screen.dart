import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_dialog.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_list_tile.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../../auth/state/auth_controller.dart';
import '../state/admin_controllers.dart';

/// Top-level admin account page (replaces the old "Profile" tab).  Combines
/// the standard account fields with the Ops controls that used to live in
/// their own bottom-nav tab — admins still need quick access to retention,
/// purge, and the migration version, but they aren't a primary navigation
/// target.
class AdminAccountScreen extends ConsumerStatefulWidget {
  const AdminAccountScreen({super.key});

  @override
  ConsumerState<AdminAccountScreen> createState() =>
      _AdminAccountScreenState();
}

class _AdminAccountScreenState extends ConsumerState<AdminAccountScreen> {
  final TextEditingController _retention = TextEditingController();
  bool _purging = false;

  @override
  void dispose() {
    _retention.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(authControllerProvider).valueOrNull;
    final ops = ref.watch(adminOpsControllerProvider);
    return Scaffold(
      appBar: AppTopBar(title: 'Account'),
      body: SafeArea(
        child: session == null
            ? const AppEmptyState(
                icon: Icons.person_outline,
                headline: 'Not signed in',
              )
            : ListView(
                children: [
                  Padding(
                    padding: const EdgeInsets.all(AppSpacing.s4),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(session.user.displayName,
                            style: context.textStyles.headlineSmall),
                        const SizedBox(height: AppSpacing.s1),
                        Text(session.user.email,
                            style:
                                context.textStyles.bodyMedium?.copyWith(
                              color: context.colors.onSurfaceVariant,
                            )),
                      ],
                    ),
                  ),
                  AppListTile(
                    leading: const Icon(Icons.settings_outlined),
                    title: 'Account settings',
                    onTap: () => context.go(AppRoutes.accountSettings),
                  ),
                  AppListTile(
                    leading: const Icon(Icons.badge_outlined),
                    title: 'Role',
                    subtitle: session.user.role,
                  ),
                  const Divider(height: AppSpacing.s6),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(
                      AppSpacing.s4,
                      AppSpacing.s2,
                      AppSpacing.s4,
                      AppSpacing.s2,
                    ),
                    child: Text('Operations',
                        style: context.textStyles.titleMedium),
                  ),
                  ops.when(
                    loading: () => const Padding(
                      padding: EdgeInsets.all(AppSpacing.s4),
                      child:
                          Center(child: CircularProgressIndicator()),
                    ),
                    error: (e, _) => Padding(
                      padding: const EdgeInsets.all(AppSpacing.s4),
                      child: AppEmptyState(
                        icon: Icons.error_outline,
                        headline: "Can't load ops",
                        subhead: '$e',
                      ),
                    ),
                    data: (s) {
                      if (_retention.text.isEmpty) {
                        _retention.text = '${s.messageRetentionDays}';
                      }
                      return Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Padding(
                            padding: const EdgeInsets.symmetric(
                                horizontal: AppSpacing.s4),
                            child: Row(
                              children: [
                                Expanded(
                                  child: AppTextField(
                                    controller: _retention,
                                    kind: AppTextFieldKind.numeric,
                                    label: 'Message retention (days)',
                                  ),
                                ),
                                const SizedBox(width: AppSpacing.s2),
                                AppButton(
                                  label: 'Save',
                                  onPressed: () async {
                                    final days =
                                        int.tryParse(_retention.text);
                                    if (days == null || days <= 0) {
                                      return;
                                    }
                                    await ref
                                        .read(
                                            adminOpsControllerProvider
                                                .notifier)
                                        .saveRetention(days);
                                    if (context.mounted) {
                                      context.showAppSnackbar(
                                          message: 'Retention saved.');
                                    }
                                  },
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: AppSpacing.s4),
                          Padding(
                            padding: const EdgeInsets.symmetric(
                                horizontal: AppSpacing.s4),
                            child: AppButton(
                              label: _purging
                                  ? 'Purging…'
                                  : 'Run message purge now',
                              variant: AppButtonVariant.destructive,
                              expand: true,
                              onPressed: _purging
                                  ? null
                                  : () async {
                                      setState(() => _purging = true);
                                      try {
                                        final count = await ref
                                            .read(
                                                adminOpsControllerProvider
                                                    .notifier)
                                            .runPurge();
                                        if (context.mounted) {
                                          context.showAppSnackbar(
                                              message:
                                                  'Purged $count messages.');
                                        }
                                      } finally {
                                        if (mounted) {
                                          setState(
                                              () => _purging = false);
                                        }
                                      }
                                    },
                            ),
                          ),
                          const SizedBox(height: AppSpacing.s2),
                          AppListTile(
                            leading: const Icon(Icons.dns_outlined),
                            title: 'Migration version',
                            trailing: Text(s.migrationVersion ?? '—',
                                style: context.textStyles.titleSmall),
                          ),
                        ],
                      );
                    },
                  ),
                  const Divider(height: AppSpacing.s6),
                  Padding(
                    padding: const EdgeInsets.all(AppSpacing.s4),
                    child: AppButton(
                      label: 'Sign out',
                      variant: AppButtonVariant.destructive,
                      expand: true,
                      onPressed: () => _confirmLogout(context, ref),
                    ),
                  ),
                ],
              ),
      ),
    );
  }

  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    await AppDialog.show(
      context,
      title: 'Sign out of this account?',
      body: const SizedBox.shrink(),
      primaryAction: AppDialogAction(
        label: 'Sign out',
        destructive: true,
        onPressed: () async {
          Navigator.of(context).pop();
          await ref.read(authControllerProvider.notifier).logout();
          if (context.mounted) {
            context.showAppSnackbar(message: 'Signed out.');
          }
        },
      ),
      secondaryAction: AppDialogAction(
        label: 'Cancel',
        onPressed: () => Navigator.of(context).pop(),
      ),
    );
  }
}
