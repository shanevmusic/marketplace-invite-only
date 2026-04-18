import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_list_tile.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../state/admin_controllers.dart';

class AdminOpsScreen extends ConsumerStatefulWidget {
  const AdminOpsScreen({super.key});

  @override
  ConsumerState<AdminOpsScreen> createState() => _AdminOpsScreenState();
}

class _AdminOpsScreenState extends ConsumerState<AdminOpsScreen> {
  final TextEditingController _retentionController = TextEditingController();
  bool _purging = false;

  @override
  void dispose() {
    _retentionController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(adminOpsControllerProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => AppEmptyState(
        icon: Icons.error_outline,
        headline: "Can't load ops",
        subhead: '$e',
      ),
      data: (s) {
        if (_retentionController.text.isEmpty) {
          _retentionController.text = '${s.messageRetentionDays}';
        }
        return ListView(
          padding: const EdgeInsets.all(AppSpacing.s4),
          children: [
            Text('Message retention',
                style: context.textStyles.titleMedium),
            const SizedBox(height: AppSpacing.s2),
            Row(
              children: [
                Expanded(
                  child: AppTextField(
                    controller: _retentionController,
                    kind: AppTextFieldKind.numeric,
                    label: 'Days',
                  ),
                ),
                const SizedBox(width: AppSpacing.s2),
                AppButton(
                  label: 'Save',
                  onPressed: () async {
                    final days = int.tryParse(_retentionController.text);
                    if (days == null || days <= 0) return;
                    await ref
                        .read(adminOpsControllerProvider.notifier)
                        .saveRetention(days);
                    if (context.mounted) {
                      context.showAppSnackbar(message: 'Retention saved.');
                    }
                  },
                ),
              ],
            ),
            const SizedBox(height: AppSpacing.s5),
            Text('Maintenance', style: context.textStyles.titleMedium),
            const SizedBox(height: AppSpacing.s2),
            AppButton(
              label: _purging ? 'Purging…' : 'Run purge now',
              variant: AppButtonVariant.destructive,
              onPressed: _purging
                  ? null
                  : () async {
                      setState(() => _purging = true);
                      try {
                        final count = await ref
                            .read(adminOpsControllerProvider.notifier)
                            .runPurge();
                        if (context.mounted) {
                          context.showAppSnackbar(
                              message: 'Purged $count messages.');
                        }
                      } finally {
                        if (mounted) setState(() => _purging = false);
                      }
                    },
            ),
            const SizedBox(height: AppSpacing.s5),
            Text('System info', style: context.textStyles.titleMedium),
            AppListTile(
              title: 'Migration version',
              trailing: Text(s.migrationVersion ?? '—',
                  style: context.textStyles.titleSmall),
            ),
            const AppListTile(
              title: 'WebSocket connections',
              subtitle: 'Real-time metrics coming soon.',
            ),
          ],
        );
      },
    );
  }
}
