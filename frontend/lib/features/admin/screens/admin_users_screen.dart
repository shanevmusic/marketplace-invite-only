import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_dialog.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_list_tile.dart';
import '../../../shared/invites/invite_link_dialog.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../../../shared/widgets/role_badge.dart';
import '../state/admin_controllers.dart';

class AdminUsersScreen extends ConsumerStatefulWidget {
  const AdminUsersScreen({super.key});

  @override
  ConsumerState<AdminUsersScreen> createState() => _AdminUsersScreenState();
}

class _AdminUsersScreenState extends ConsumerState<AdminUsersScreen> {
  final TextEditingController _search = TextEditingController();
  String? _role;
  String? _status;

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  void _apply() {
    ref.read(adminUsersControllerProvider.notifier).applyFilter(
          AdminUsersFilter(
            q: _search.text.trim().isEmpty ? null : _search.text.trim(),
            role: _role,
            status: _status,
          ),
        );
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(adminUsersControllerProvider);
    return Scaffold(
      body: Column(
        children: [
          Padding(
            padding: const EdgeInsets.all(AppSpacing.s4),
            child: AppTextField(
              controller: _search,
              label: 'Search users',
              hint: 'email or name',
              onSubmitted: (_) => _apply(),
            ),
          ),
          _FilterRow(
            role: _role,
            status: _status,
            onRoleChanged: (v) {
              setState(() => _role = v);
              _apply();
            },
            onStatusChanged: (v) {
              setState(() => _status = v);
              _apply();
            },
          ),
          Expanded(
            child: async.when(
              loading: () =>
                  const Center(child: CircularProgressIndicator()),
              error: (e, _) => AppEmptyState(
                icon: Icons.error_outline,
                headline: "Can't load users",
                subhead: '$e',
              ),
              data: (s) => _UsersList(state: s),
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showIssueInvite(context, ref),
        icon: const Icon(Icons.person_add_alt_1),
        label: const Text('Issue invite'),
      ),
    );
  }
}

class _FilterRow extends StatelessWidget {
  const _FilterRow({
    required this.role,
    required this.status,
    required this.onRoleChanged,
    required this.onStatusChanged,
  });
  final String? role;
  final String? status;
  final ValueChanged<String?> onRoleChanged;
  final ValueChanged<String?> onStatusChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: AppSpacing.s4),
      child: Row(
        children: [
          Expanded(
            child: DropdownButton<String?>(
              isExpanded: true,
              value: role,
              hint: const Text('All roles'),
              items: const [
                DropdownMenuItem(value: null, child: Text('All roles')),
                DropdownMenuItem(value: 'admin', child: Text('Admin')),
                DropdownMenuItem(value: 'seller', child: Text('Seller')),
                DropdownMenuItem(value: 'customer', child: Text('Customer')),
                DropdownMenuItem(value: 'driver', child: Text('Driver')),
              ],
              onChanged: onRoleChanged,
            ),
          ),
          const SizedBox(width: AppSpacing.s3),
          Expanded(
            child: DropdownButton<String?>(
              isExpanded: true,
              value: status,
              hint: const Text('All statuses'),
              items: const [
                DropdownMenuItem(value: null, child: Text('All statuses')),
                DropdownMenuItem(value: 'active', child: Text('Active')),
                DropdownMenuItem(
                    value: 'suspended', child: Text('Suspended')),
              ],
              onChanged: onStatusChanged,
            ),
          ),
        ],
      ),
    );
  }
}

class _UsersList extends ConsumerWidget {
  const _UsersList({required this.state});
  final AdminUsersState state;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (state.users.isEmpty) {
      return const AppEmptyState(
        icon: Icons.people_outline,
        headline: 'No users match this filter.',
      );
    }
    return NotificationListener<ScrollNotification>(
      onNotification: (n) {
        if (n.metrics.pixels >= n.metrics.maxScrollExtent - 200) {
          ref.read(adminUsersControllerProvider.notifier).loadMore();
        }
        return false;
      },
      child: ListView.builder(
        itemCount: state.users.length + (state.isLoadingMore ? 1 : 0),
        itemBuilder: (context, i) {
          if (i >= state.users.length) {
            return const Padding(
              padding: EdgeInsets.all(AppSpacing.s4),
              child: Center(child: CircularProgressIndicator()),
            );
          }
          final u = state.users[i];
          return AppListTile(
            leading: CircleAvatar(
              child: Text(u.displayName.isNotEmpty
                  ? u.displayName[0].toUpperCase()
                  : '?'),
            ),
            title: u.displayName,
            subtitle: u.email,
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                RoleBadge(role: u.role),
                const SizedBox(width: AppSpacing.s2),
                _StatusChip(status: u.status),
              ],
            ),
            onTap: () =>
                _showUserDetail(context, ref, u.id),
          );
        },
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final isSuspended = status == 'suspended';
    return Container(
      padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s2, vertical: 2),
      decoration: BoxDecoration(
        color: isSuspended ? colors.errorContainer : colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Text(
        status.toUpperCase(),
        style: context.textStyles.labelSmall?.copyWith(
          color: isSuspended ? colors.onErrorContainer : colors.onSurface,
        ),
      ),
    );
  }
}

Future<void> _showUserDetail(
    BuildContext context, WidgetRef ref, String userId) async {
  await showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,
    builder: (_) {
      return FractionallySizedBox(
        heightFactor: 0.9,
        child: _UserDetailSheet(userId: userId),
      );
    },
  );
}

class _UserDetailSheet extends ConsumerWidget {
  const _UserDetailSheet({required this.userId});
  final String userId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(adminUserDetailProvider(userId));
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => Center(child: Text('Error: $e')),
      data: (detail) {
        final u = detail.user;
        return SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.s4),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(u.displayName, style: context.textStyles.headlineSmall),
                const SizedBox(height: AppSpacing.s1),
                Text(u.email, style: context.textStyles.bodyMedium),
                const SizedBox(height: AppSpacing.s2),
                Row(children: [
                  RoleBadge(role: u.role),
                  const SizedBox(width: AppSpacing.s2),
                  _StatusChip(status: u.status),
                ]),
                const SizedBox(height: AppSpacing.s4),
                if (u.status == 'suspended') ...[
                  AppButton(
                    label: 'Unsuspend',
                    onPressed: () async {
                      await ref
                          .read(adminUsersControllerProvider.notifier)
                          .unsuspend(u.id);
                      ref.invalidate(adminUserDetailProvider(userId));
                      if (context.mounted) {
                        Navigator.of(context).pop();
                        context.showAppSnackbar(message: 'User unsuspended.');
                      }
                    },
                  ),
                ] else ...[
                  AppButton(
                    label: 'Suspend',
                    variant: AppButtonVariant.destructive,
                    onPressed: () => _promptSuspend(context, ref, u.id),
                  ),
                ],
                const SizedBox(height: AppSpacing.s4),
                Text('Invite tree', style: context.textStyles.titleMedium),
                const SizedBox(height: AppSpacing.s2),
                if (detail.referredBy != null)
                  AppListTile(
                    title: 'Referred by ${detail.referredBy!.displayName}',
                    subtitle: detail.referredBy!.email,
                  )
                else
                  const AppListTile(
                      title: 'Joined via admin invite or seed'),
                const SizedBox(height: AppSpacing.s3),
                Text('Referred users (${detail.referredUsers.length})',
                    style: context.textStyles.titleMedium),
                for (final r in detail.referredUsers)
                  AppListTile(
                    title: r.displayName,
                    subtitle: r.email,
                    trailing: RoleBadge(role: r.role),
                  ),
              ],
            ),
          ),
        );
      },
    );
  }
}

Future<void> _promptSuspend(
    BuildContext context, WidgetRef ref, String userId) async {
  final controller = TextEditingController();
  await AppDialog.show(
    context,
    title: 'Suspend user?',
    body: AppTextField(
      controller: controller,
      label: 'Reason',
      hint: 'Required (1–500 chars)',
    ),
    primaryAction: AppDialogAction(
      label: 'Suspend',
      destructive: true,
      onPressed: () async {
        final reason = controller.text.trim();
        if (reason.isEmpty) return;
        Navigator.of(context).pop();
        await ref
            .read(adminUsersControllerProvider.notifier)
            .suspend(userId, reason);
        ref.invalidate(adminUserDetailProvider(userId));
        if (context.mounted) {
          Navigator.of(context).pop();
          context.showAppSnackbar(message: 'User suspended.');
        }
      },
    ),
    secondaryAction: AppDialogAction(
      label: 'Cancel',
      onPressed: () => Navigator.of(context).pop(),
    ),
  );
}

Future<void> _showIssueInvite(BuildContext context, WidgetRef ref) async {
  String role = 'seller';
  final daysController = TextEditingController(text: '7');
  await AppDialog.show(
    context,
    title: 'Issue invite',
    body: StatefulBuilder(
      builder: (context, setState) {
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            DropdownButton<String>(
              value: role,
              isExpanded: true,
              items: const [
                DropdownMenuItem(value: 'admin', child: Text('Admin')),
                DropdownMenuItem(value: 'seller', child: Text('Seller')),
                DropdownMenuItem(value: 'customer', child: Text('Customer')),
                DropdownMenuItem(value: 'driver', child: Text('Driver')),
              ],
              onChanged: (v) => setState(() => role = v ?? 'seller'),
            ),
            const SizedBox(height: AppSpacing.s3),
            AppTextField(
              controller: daysController,
              kind: AppTextFieldKind.numeric,
              label: 'Expires in days',
            ),
          ],
        );
      },
    ),
    primaryAction: AppDialogAction(
      label: 'Create',
      onPressed: () async {
        final days = int.tryParse(daysController.text) ?? 7;
        Navigator.of(context).pop();
        try {
          final invite = await ref
              .read(adminApiProvider)
              .issueInvite(roleTarget: role, expiresInDays: days);
          if (context.mounted) {
            InviteLinkSheet.show(
              context,
              token: invite.token,
              title: 'Invite created',
              roleTarget: invite.roleTarget,
              subtitle: invite.expiresAt != null
                  ? 'Single-use invite for a new $role. Expires '
                      '${invite.expiresAt!.toLocal().toString().split('.').first}.'
                  : 'Single-use invite for a new $role.',
            );
          }
        } catch (e) {
          if (context.mounted) {
            context.showAppSnackbar(message: 'Failed: $e');
          }
        }
      },
    ),
    secondaryAction: AppDialogAction(
      label: 'Cancel',
      onPressed: () => Navigator.of(context).pop(),
    ),
  );
}
