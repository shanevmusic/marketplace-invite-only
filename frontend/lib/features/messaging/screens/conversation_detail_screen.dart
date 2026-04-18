import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../../../shared/widgets/chat_bubble.dart';
import '../application/conversation_controller.dart';
import '../widgets/message_composer.dart';
import '../widgets/typing_indicator.dart';

class ConversationDetailScreen extends ConsumerWidget {
  const ConversationDetailScreen({
    super.key,
    required this.conversationId,
  });

  final String conversationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(conversationControllerProvider(conversationId));
    return Scaffold(
      appBar: AppTopBar(title: 'Conversation'),
      body: async.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (_, __) => const AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Conversation unavailable',
        ),
        data: (s) {
          if (s.localKeyMissing) {
            return Center(
              child: Padding(
                padding: const EdgeInsets.all(AppSpacing.s4),
                child: Text(
                  'Set up encryption on this device to read messages.',
                  textAlign: TextAlign.center,
                  style: context.textStyles.bodyMedium,
                ),
              ),
            );
          }
          return Column(
            children: [
              Expanded(
                child: ListView.builder(
                  reverse: true,
                  padding: const EdgeInsets.symmetric(
                    horizontal: AppSpacing.s4,
                    vertical: AppSpacing.s3,
                  ),
                  itemCount: s.messages.length,
                  itemBuilder: (_, i) {
                    final m = s.messages[s.messages.length - 1 - i];
                    return ChatBubble(
                      text: m.text,
                      isMine: m.isMine,
                      sentAt: m.sentAt,
                      status: m.status,
                      onRetry: m.status == MessageStatus.failed
                          ? () => ref
                              .read(
                                  conversationControllerProvider(conversationId)
                                      .notifier)
                              .send(m.text)
                          : null,
                    );
                  },
                ),
              ),
              if (s.peerIsTyping)
                TypingIndicator(peerDisplayName: s.peerDisplayName),
              MessageComposer(
                enabled: s.peerHasKey,
                peerFirstName: s.peerDisplayName.isNotEmpty
                    ? s.peerDisplayName.split(' ').first
                    : 'them',
                onSend: (text) => ref
                    .read(
                        conversationControllerProvider(conversationId).notifier)
                    .send(text),
                onTypingChanged: (t) => ref
                    .read(
                        conversationControllerProvider(conversationId).notifier)
                    .setTyping(t),
              ),
            ],
          );
        },
      ),
    );
  }
}
