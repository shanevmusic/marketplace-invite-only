import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../state/delivery_flow_providers.dart';

/// Admin-only forensic view: full tracking breadcrumb + archived ciphertext.
class AdminOrderTrackingScreen extends ConsumerWidget {
  const AdminOrderTrackingScreen({super.key, required this.orderId});
  final String orderId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final tracking = ref.watch(adminTrackingProvider(orderId));
    final messages = ref.watch(adminMessagesProvider(orderId));
    final t = context.textStyles;

    return DefaultTabController(
      length: 2,
      child: Scaffold(
        appBar: AppTopBar(
          title: 'Order tracking',
          trailing: const [],
        ),
        body: Column(
          children: [
            const TabBar(
              tabs: [
                Tab(text: 'Tracking'),
                Tab(text: 'Messages (archived)'),
              ],
            ),
            Expanded(
              child: TabBarView(
                children: [
                  tracking.when(
                    loading: () =>
                        const Center(child: CircularProgressIndicator()),
                    error: (_, __) =>
                        const Center(child: Text('Failed to load')),
                    data: (points) => ListView.separated(
                      padding: const EdgeInsets.all(16),
                      itemCount: points.length,
                      separatorBuilder: (_, __) => const Divider(),
                      itemBuilder: (_, i) {
                        final p = points[i];
                        return ListTile(
                          leading: const Icon(Icons.location_on),
                          title: Text(
                            '${p['lat']}, ${p['lng']}',
                            style: t.bodyMedium,
                          ),
                          subtitle: Text(
                            (p['recorded_at'] as String?) ?? '',
                            style: t.bodySmall,
                          ),
                        );
                      },
                    ),
                  ),
                  messages.when(
                    loading: () =>
                        const Center(child: CircularProgressIndicator()),
                    error: (_, __) =>
                        const Center(child: Text('Failed to load')),
                    data: (msgs) => ListView.separated(
                      padding: const EdgeInsets.all(16),
                      itemCount: msgs.length,
                      separatorBuilder: (_, __) => const Divider(),
                      itemBuilder: (_, i) {
                        final m = msgs[i];
                        return ListTile(
                          leading: Icon(
                            (m['sender_role'] == 'driver')
                                ? Icons.local_shipping
                                : Icons.person,
                          ),
                          title: Text(
                            (m['ciphertext'] as String?) ?? '',
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                            style: t.bodySmall,
                          ),
                          subtitle: Text(
                            '${m['sender_role']} • ${m['created_at']}',
                            style: t.bodySmall,
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}
