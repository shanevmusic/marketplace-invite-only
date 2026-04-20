import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_list_tile.dart';
import '../state/admin_controllers.dart';

/// Admin → Drivers tab.  Reuses ``GET /admin/users?role=driver`` so we get
/// the existing pagination + suspension surface for free.  Tapping a driver
/// opens the same detail sheet used by the Users screen (via the shared
/// ``adminUserDetailProvider``); for now we keep this screen read-only and
/// route admins to the Users tab for suspend/unsuspend actions to avoid
/// duplicating the full sheet plumbing.
class AdminDriversScreen extends ConsumerWidget {
  const AdminDriversScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(adminDriversControllerProvider);
    return Scaffold(
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => AppEmptyState(
          icon: Icons.error_outline,
          headline: "Can't load drivers",
          subhead: '$e',
        ),
        data: (s) {
          if (s.drivers.isEmpty) {
            return const AppEmptyState(
              icon: Icons.local_shipping_outlined,
              headline: 'No drivers yet',
              subhead:
                  'Issue a driver invite from the Users tab to onboard one.',
            );
          }
          return RefreshIndicator(
            onRefresh: () =>
                ref.read(adminDriversControllerProvider.notifier).refresh(),
            child: NotificationListener<ScrollNotification>(
              onNotification: (n) {
                if (n.metrics.pixels >= n.metrics.maxScrollExtent - 200) {
                  ref
                      .read(adminDriversControllerProvider.notifier)
                      .loadMore();
                }
                return false;
              },
              child: ListView.builder(
                itemCount: s.drivers.length + (s.isLoadingMore ? 1 : 0),
                itemBuilder: (context, i) {
                  if (i >= s.drivers.length) {
                    return const Padding(
                      padding: EdgeInsets.all(AppSpacing.s4),
                      child: Center(child: CircularProgressIndicator()),
                    );
                  }
                  final d = s.drivers[i];
                  return AppListTile(
                    leading: CircleAvatar(
                      child: Text(d.displayName.isNotEmpty
                          ? d.displayName[0].toUpperCase()
                          : '?'),
                    ),
                    title: d.displayName,
                    subtitle: d.email,
                    trailing: _DriverStatusChip(status: d.status),
                  );
                },
              ),
            ),
          );
        },
      ),
    );
  }
}

class _DriverStatusChip extends StatelessWidget {
  const _DriverStatusChip({required this.status});
  final String status;

  @override
  Widget build(BuildContext context) {
    final colors = context.colors;
    final isSuspended = status == 'suspended';
    return Container(
      padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s2, vertical: 2),
      decoration: BoxDecoration(
        color: isSuspended
            ? colors.errorContainer
            : colors.surfaceContainerHighest,
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
