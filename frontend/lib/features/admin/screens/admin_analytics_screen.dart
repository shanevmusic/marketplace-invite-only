import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/format/money.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/app_list_tile.dart';
import '../state/admin_controllers.dart';

class AdminAnalyticsScreen extends ConsumerWidget {
  const AdminAnalyticsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(adminAnalyticsControllerProvider);
    return async.when(
      loading: () => const Center(child: CircularProgressIndicator()),
      error: (e, _) => AppEmptyState(
        icon: Icons.error_outline,
        headline: "Can't load analytics",
        subhead: '$e',
      ),
      data: (s) {
        return RefreshIndicator(
          onRefresh: () =>
              ref.read(adminAnalyticsControllerProvider.notifier).refresh(),
          child: ListView(
            padding: const EdgeInsets.all(AppSpacing.s4),
            children: [
              _KpiStrip(
                gmv: s.overview.totalGmvMinor,
                orders: s.overview.ordersCount,
                active30d: s.overview.activeUsers30d,
                sellers: s.overview.sellerCount,
              ),
              const SizedBox(height: AppSpacing.s4),
              _SectionTitle('Active users'),
              _KvRow(label: 'Last 24h', value: '${s.overview.activeUsers24h}'),
              _KvRow(label: 'Last 7d', value: '${s.overview.activeUsers7d}'),
              _KvRow(label: 'Last 30d', value: '${s.overview.activeUsers30d}'),
              const SizedBox(height: AppSpacing.s4),
              _SectionTitle('Role breakdown'),
              _KvRow(label: 'Admins', value: '${s.overview.adminCount}'),
              _KvRow(label: 'Sellers', value: '${s.overview.sellerCount}'),
              _KvRow(
                  label: 'Customers', value: '${s.overview.customerCount}'),
              _KvRow(label: 'Drivers', value: '${s.overview.driverCount}'),
              const SizedBox(height: AppSpacing.s4),
              _SectionTitle('Top sellers'),
              if (s.topSellers.isEmpty)
                const AppEmptyState(
                  icon: Icons.trending_up,
                  headline: 'No sales yet',
                ),
              for (final t in s.topSellers)
                AppListTile(
                  title: t.displayName,
                  subtitle:
                      '${t.lifetimeOrderCount} orders · ${formatMoney(t.lifetimeRevenueMinor)}',
                ),
            ],
          ),
        );
      },
    );
  }
}

class _KpiStrip extends StatelessWidget {
  const _KpiStrip({
    required this.gmv,
    required this.orders,
    required this.active30d,
    required this.sellers,
  });
  final int gmv;
  final int orders;
  final int active30d;
  final int sellers;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        _KpiCard(label: 'GMV', value: formatMoney(gmv)),
        const SizedBox(width: AppSpacing.s2),
        _KpiCard(label: 'Orders', value: '$orders'),
        const SizedBox(width: AppSpacing.s2),
        _KpiCard(label: 'Active 30d', value: '$active30d'),
        const SizedBox(width: AppSpacing.s2),
        _KpiCard(label: 'Sellers', value: '$sellers'),
      ],
    );
  }
}

class _KpiCard extends StatelessWidget {
  const _KpiCard({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Container(
        padding: const EdgeInsets.all(AppSpacing.s3),
        decoration: BoxDecoration(
          color: context.colors.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(label,
                style: context.textStyles.labelSmall?.copyWith(
                  color: context.colors.onSurfaceVariant,
                )),
            const SizedBox(height: 2),
            Text(value,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: context.textStyles.titleMedium),
          ],
        ),
      ),
    );
  }
}

class _SectionTitle extends StatelessWidget {
  const _SectionTitle(this.title);
  final String title;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.s2),
      child: Text(title, style: context.textStyles.titleMedium),
    );
  }
}

class _KvRow extends StatelessWidget {
  const _KvRow({required this.label, required this.value});
  final String label;
  final String value;
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: AppSpacing.s1),
      child: Row(
        children: [
          Expanded(child: Text(label, style: context.textStyles.bodyMedium)),
          Text(value, style: context.textStyles.titleSmall),
        ],
      ),
    );
  }
}
