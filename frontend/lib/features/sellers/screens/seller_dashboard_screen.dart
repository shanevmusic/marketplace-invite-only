import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/invites/invite_link_dialog.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/metric_card.dart';
import '../../stores/state/store_controller.dart';
import '../data/seller_dtos.dart';
import '../state/seller_controller.dart';

class SellerDashboardScreen extends ConsumerWidget {
  const SellerDashboardScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final storeAsync = ref.watch(myStoreControllerProvider);
    return storeAsync.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (_, __) => AppEmptyState(
        icon: Icons.error_outline,
        headline: 'Could not load your store',
        ctaLabel: 'Retry',
        onCtaPressed: () =>
            ref.read(myStoreControllerProvider.notifier).refresh(),
      ),
      data: (store) {
        if (store == null) {
          return AppEmptyState(
            icon: Icons.storefront_outlined,
            headline: 'Create your store',
            subhead: 'Give it a name and city so customers can find you.',
            ctaLabel: 'Create store',
            onCtaPressed: () =>
                context.go('${AppRoutes.sellerDashboard}/store/new'),
          );
        }
        final dashAsync = ref.watch(sellerDashboardControllerProvider);
        return RefreshIndicator(
          onRefresh: () =>
              ref.read(sellerDashboardControllerProvider.notifier).refresh(),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.s4),
            children: [
              dashAsync.when(
                loading: () => const Padding(
                  padding: EdgeInsets.symmetric(vertical: AppSpacing.s5),
                  child: Center(child: CircularProgressIndicator()),
                ),
                error: (e, _) => MetricCard(
                  label: 'Dashboard',
                  value: '—',
                  caption: 'Pull to retry',
                ),
                data: (d) => Column(
                  children: [
                    MetricCard(
                      label: 'Lifetime sales',
                      value: formatMoney(d.lifetimeSalesMinor,
                          currencyCode: d.currencyCode),
                    ),
                    const SizedBox(height: AppSpacing.s3),
                    MetricCard(
                      label: 'Lifetime orders',
                      value: '${d.lifetimeOrdersCount}',
                    ),
                    const SizedBox(height: AppSpacing.s3),
                    MetricCard(
                      label: 'Active orders',
                      value: '${d.activeOrdersCount}',
                      onTap: () => context.go(AppRoutes.sellerOrders),
                    ),
                    const SizedBox(height: AppSpacing.s3),
                    MetricCard(
                      label: 'Invite a customer or seller',
                      value: 'Share link',
                      caption: 'Tap to get your referral link',
                      trailing: const Icon(Icons.share_outlined),
                      onTap: () => _openInviteSheet(context, ref),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Future<void> _openInviteSheet(BuildContext context, WidgetRef ref) async {
    final api = ref.read(sellerApiProvider);
    SellerInvite invite;
    try {
      invite = await api.getOrCreateReferral();
    } catch (e) {
      if (context.mounted) {
        context.showAppSnackbar(message: 'Could not load invite: $e');
      }
      return;
    }
    if (!context.mounted) return;
    await InviteLinkSheet.show(
      context,
      token: invite.token,
      title: 'Your referral link',
      subtitle:
          'Share this with anyone who should join. They\'ll land on the signup page — no email required. '
          '${invite.usedCount} signup${invite.usedCount == 1 ? '' : 's'} so far.',
      onRegenerate: () async {
        try {
          final fresh = await api.regenerateReferral();
          if (!context.mounted) return;
          context.showAppSnackbar(message: 'New link generated');
          await InviteLinkSheet.show(
            context,
            token: fresh.token,
            title: 'Your referral link',
            subtitle:
                'Old link is now invalid. Share this new one with anyone who should join.',
            onRegenerate: () {},
          );
        } catch (e) {
          if (context.mounted) {
            context.showAppSnackbar(message: 'Failed to regenerate: $e');
          }
        }
      },
    );
  }
}
