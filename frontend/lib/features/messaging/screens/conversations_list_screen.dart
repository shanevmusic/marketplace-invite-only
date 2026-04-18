import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../auth/state/auth_controller.dart';
import '../application/conversations_controller.dart';

class ConversationsListScreen extends ConsumerWidget {
  const ConversationsListScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authControllerProvider).valueOrNull;
    final isCustomer = session?.user.role == 'customer';
    final isUnreferred = isCustomer && session?.user.referringSellerId == null;

    if (isUnreferred) {
      return Scaffold(
        appBar: AppTopBar(title: 'Messages'),
        body: const AppEmptyState(
          icon: Icons.lock_outline,
          headline: 'You need a seller invite',
          subhead: 'Messages unlock when a seller invites you.',
        ),
      );
    }

    final async = ref.watch(conversationsControllerProvider);

    return Scaffold(
      appBar: AppTopBar(title: 'Messages'),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const AppEmptyState(
          icon: Icons.wifi_off,
          headline: "Can't load messages",
        ),
        data: (convos) {
          if (convos.isEmpty) {
            return const AppEmptyState(
              icon: Icons.chat_bubble_outline,
              headline: 'No messages yet',
              subhead:
                  'Tap the chat icon on a store or order to start a conversation.',
            );
          }
          return ListView.separated(
            padding: const EdgeInsets.all(AppSpacing.s2),
            itemCount: convos.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (_, i) {
              final c = convos[i];
              return ListTile(
                leading: const CircleAvatar(child: Icon(Icons.person)),
                title: Text(c.peerDisplayName),
                subtitle: Text(
                  c.lastMessagePreview ?? '🔒 End-to-end encrypted',
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: context.textStyles.bodySmall?.copyWith(
                    color: context.colors.onSurfaceVariant,
                  ),
                ),
                trailing: c.unreadCount > 0
                    ? CircleAvatar(
                        radius: 10,
                        backgroundColor: context.colors.primary,
                        child: Text(
                          '${c.unreadCount}',
                          style: context.textStyles.labelSmall?.copyWith(
                            color: context.colors.onPrimary,
                          ),
                        ),
                      )
                    : null,
                onTap: () {
                  // Navigation resolved by parent shell — stub for now.
                },
              );
            },
          );
        },
      ),
    );
  }
}
