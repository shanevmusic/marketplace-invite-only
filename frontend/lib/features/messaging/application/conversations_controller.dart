import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../auth/state/auth_controller.dart';
import '../data/messaging_api.dart';
import '../domain/message_view.dart';

/// Inbox controller. ADR-0007: unreferred customers bypass the API call
/// entirely — see [build]. The WS layer auto-subscribes participant
/// conversations server-side on connect, so we don't need to subscribe each
/// channel from here.
class ConversationsController extends AsyncNotifier<List<ConversationView>> {
  @override
  Future<List<ConversationView>> build() async {
    final session = ref.read(authControllerProvider).valueOrNull;
    if (session == null) return const [];
    // ADR-0007 — unreferred customer sees the empty-state; no API call.
    if (session.user.role == 'customer' &&
        session.user.referringSellerId == null) {
      return const [];
    }
    final dtos = await ref.read(messagingApiProvider).listConversations();
    final ownId = session.user.id;
    return [
      for (final c in dtos)
        ConversationView(
          id: c.id,
          peerId: c.participantIds.firstWhere(
            (p) => p != ownId,
            orElse: () =>
                c.participantIds.isEmpty ? '' : c.participantIds.first,
          ),
          peerDisplayName: '…',
          lastMessageAt: c.lastMessageAt,
          unreadCount: c.unreadCount,
        ),
    ];
  }

  void bumpOnNewMessage({
    required String conversationId,
    required String senderId,
    required DateTime sentAt,
  }) {
    final own = ref.read(authControllerProvider).valueOrNull?.user.id;
    final cur = state.value;
    if (cur == null) return;
    final idx = cur.indexWhere((c) => c.id == conversationId);
    if (idx < 0) return;
    final target = cur[idx];
    final isFromMe = senderId == own;
    final updated = target.copyWith(
      lastMessageAt: sentAt,
      unreadCount: isFromMe ? target.unreadCount : target.unreadCount + 1,
    );
    final next = [...cur]
      ..removeAt(idx)
      ..insert(0, updated);
    state = AsyncValue.data(next);
  }
}

final conversationsControllerProvider =
    AsyncNotifierProvider<ConversationsController, List<ConversationView>>(
        ConversationsController.new);
