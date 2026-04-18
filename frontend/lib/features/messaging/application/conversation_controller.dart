import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import '../../../shared/widgets/chat_bubble.dart';
import '../../auth/state/auth_controller.dart';
import '../../realtime/ws_client.dart';
import '../../realtime/ws_event.dart';
import '../crypto/crypto_service.dart';
import '../crypto/key_store.dart';
import '../data/messaging_api.dart';
import '../data/messaging_dtos.dart';
import '../domain/message_view.dart';

final cryptoServiceProvider = Provider<MessagingCryptoService>(
  (_) => MessagingCryptoService(),
);

final keyStoreProvider = Provider<MessagingKeyStore>(
  (_) => MessagingKeyStore(),
);

class ConversationScreenState {
  const ConversationScreenState({
    required this.messages,
    required this.peerHasKey,
    required this.localKeyMissing,
    required this.peerIsTyping,
    this.peerDisplayName = '',
  });

  final List<MessageView> messages;
  final bool peerHasKey;
  final bool localKeyMissing;
  final bool peerIsTyping;
  final String peerDisplayName;

  ConversationScreenState copyWith({
    List<MessageView>? messages,
    bool? peerHasKey,
    bool? localKeyMissing,
    bool? peerIsTyping,
    String? peerDisplayName,
  }) =>
      ConversationScreenState(
        messages: messages ?? this.messages,
        peerHasKey: peerHasKey ?? this.peerHasKey,
        localKeyMissing: localKeyMissing ?? this.localKeyMissing,
        peerIsTyping: peerIsTyping ?? this.peerIsTyping,
        peerDisplayName: peerDisplayName ?? this.peerDisplayName,
      );

  static const empty = ConversationScreenState(
    messages: [],
    peerHasKey: true,
    localKeyMissing: false,
    peerIsTyping: false,
  );
}

class ConversationController
    extends FamilyAsyncNotifier<ConversationScreenState, String> {
  StreamSubscription<WsEvent>? _sub;
  Timer? _typingClear;
  PeerKeyDto? _peerKey;
  StoredKeypair? _ownKey;

  @override
  Future<ConversationScreenState> build(String conversationId) async {
    final api = ref.read(messagingApiProvider);
    final crypto = ref.read(cryptoServiceProvider);
    final ks = ref.read(keyStoreProvider);
    final session = ref.read(authControllerProvider).valueOrNull;
    if (session == null) return ConversationScreenState.empty;

    final convoDtos = await api.listConversations();
    final convo = convoDtos.firstWhere(
      (c) => c.id == conversationId,
      orElse: () => throw ApiException(statusCode: 404, code: 'NOT_FOUND'),
    );
    final peerId = convo.participantIds.firstWhere(
      (p) => p != session.user.id,
      orElse: () => '',
    );

    _peerKey = await api.getPeerKey(peerId);
    _ownKey = await ks.readActive();

    final envelopes = await api.listMessages(conversationId);
    final decrypted = <MessageView>[];
    for (final env in envelopes) {
      final view = await _decryptToView(env, crypto, ks, session.user.id);
      decrypted.add(view);
    }
    decrypted.sort((a, b) => a.sentAt.compareTo(b.sentAt));

    _subscribe(conversationId, crypto, ks, session.user.id);
    ref.onDispose(() {
      _sub?.cancel();
      _typingClear?.cancel();
      ref.read(wsClientProvider).unsubscribe(
            conversationChannel(conversationId),
          );
    });

    return ConversationScreenState(
      messages: decrypted,
      peerHasKey: _peerKey != null,
      localKeyMissing: _ownKey == null,
      peerIsTyping: false,
    );
  }

  Future<MessageView> _decryptToView(
    MessageEnvelopeDto env,
    MessagingCryptoService crypto,
    MessagingKeyStore ks,
    String ownId,
  ) async {
    final isMine = env.senderId == ownId;
    final status = env.readAt != null
        ? MessageStatus.read
        : isMine
            ? MessageStatus.sent
            : MessageStatus.sent;

    final kp = await ks.readByKeyId(env.recipientKeyId);
    if (kp == null) {
      return MessageView(
        id: env.id,
        text: '',
        isMine: isMine,
        sentAt: env.sentAt,
        status: MessageStatus.decryptionError,
      );
    }
    try {
      final plain = await crypto.decryptWith(
        privateKey: kp.privateKey,
        ciphertextB64: env.ciphertext,
        nonceB64: env.nonce,
        ephemeralPublicKeyB64: env.ephemeralPublicKey,
      );
      return MessageView(
        id: env.id,
        text: plain,
        isMine: isMine,
        sentAt: env.sentAt,
        status: status,
        readAt: env.readAt,
      );
    } catch (_) {
      return MessageView(
        id: env.id,
        text: '',
        isMine: isMine,
        sentAt: env.sentAt,
        status: MessageStatus.decryptionError,
      );
    }
  }

  void _subscribe(
    String conversationId,
    MessagingCryptoService crypto,
    MessagingKeyStore ks,
    String ownId,
  ) {
    final ws = ref.read(wsClientProvider);
    ws.subscribe(conversationChannel(conversationId));
    _sub = ws.events.listen((ev) {
      if (ev.channel != conversationChannel(conversationId)) return;
      switch (ev.type) {
        case 'message.new':
          _handleMessageNew(ev, crypto, ks, ownId);
          break;
        case 'message.read':
          _handleMessageRead(ev, ownId);
          break;
        case 'typing':
          _handleTyping(ev, ownId);
          break;
      }
    });
  }

  Future<void> _handleMessageNew(
    WsEvent ev,
    MessagingCryptoService crypto,
    MessagingKeyStore ks,
    String ownId,
  ) async {
    final cur = state.value;
    if (cur == null) return;
    try {
      final env = MessageEnvelopeDto.fromJson({
        'id': ev.data['message_id'] ?? ev.data['id'],
        'conversation_id': ev.data['conversation_id'],
        'sender_id': ev.data['sender_id'],
        'ciphertext': ev.data['ciphertext'],
        'nonce': ev.data['nonce'],
        'ephemeral_public_key': ev.data['ephemeral_public_key'],
        'recipient_key_id': ev.data['recipient_key_id'],
        'sent_at': ev.data['sent_at'],
      });
      if (cur.messages.any((m) => m.id == env.id)) return;
      final v = await _decryptToView(env, crypto, ks, ownId);
      state = AsyncValue.data(cur.copyWith(
        messages: [...cur.messages, v],
      ));
    } catch (_) {
      // dropped — schema mismatch, do not propagate noise.
    }
  }

  void _handleMessageRead(WsEvent ev, String ownId) {
    final cur = state.value;
    if (cur == null) return;
    final readerId = ev.data['reader_id'] as String?;
    if (readerId == null || readerId == ownId) return;
    final mid = ev.data['message_id'] as String?;
    if (mid == null) return;
    final updated = [
      for (final m in cur.messages)
        if (m.id == mid)
          m.copyWith(status: MessageStatus.read, readAt: DateTime.now())
        else
          m,
    ];
    state = AsyncValue.data(cur.copyWith(messages: updated));
  }

  void _handleTyping(WsEvent ev, String ownId) {
    final cur = state.value;
    if (cur == null) return;
    final userId = ev.data['user_id'] as String?;
    final typing = ev.data['is_typing'] as bool? ?? false;
    if (userId == null || userId == ownId) return;
    state = AsyncValue.data(cur.copyWith(peerIsTyping: typing));
    _typingClear?.cancel();
    if (typing) {
      _typingClear = Timer(const Duration(seconds: 5), () {
        final s = state.value;
        if (s != null) state = AsyncValue.data(s.copyWith(peerIsTyping: false));
      });
    }
  }

  /// Optimistic send: encrypt, POST, update state. Fails → status=failed.
  Future<void> send(String plaintext) async {
    final conversationId = arg;
    final cur = state.value;
    if (cur == null) return;
    final peerKey = _peerKey;
    if (peerKey == null) return;
    final crypto = ref.read(cryptoServiceProvider);
    final session = ref.read(authControllerProvider).valueOrNull;
    if (session == null) return;

    final tmpId = 'tmp-${DateTime.now().microsecondsSinceEpoch}';
    final optimistic = MessageView(
      id: tmpId,
      text: plaintext,
      isMine: true,
      sentAt: DateTime.now(),
      status: MessageStatus.sending,
    );
    state =
        AsyncValue.data(cur.copyWith(messages: [...cur.messages, optimistic]));

    try {
      final peerPub = Uint8List.fromList(base64Decode(peerKey.publicKey));
      final env = await crypto.encryptFor(
        peerPublicKey: peerPub,
        plaintext: plaintext,
      );
      final outbound = MessageEnvelopeDto(
        id: tmpId,
        conversationId: conversationId,
        senderId: session.user.id,
        ciphertext: env.ciphertext,
        nonce: env.nonce,
        ephemeralPublicKey: env.ephemeralPublicKey,
        recipientKeyId: peerKey.id,
        sentAt: DateTime.now(),
      );
      final sent = await ref
          .read(messagingApiProvider)
          .sendMessage(conversationId, outbound);
      final cur2 = state.value;
      if (cur2 == null) return;
      final replaced = [
        for (final m in cur2.messages)
          if (m.id == tmpId)
            m.copyWith(
                id: sent.id, status: MessageStatus.sent, sentAt: sent.sentAt)
          else
            m,
      ];
      state = AsyncValue.data(cur2.copyWith(messages: replaced));
    } catch (_) {
      final cur2 = state.value;
      if (cur2 == null) return;
      final replaced = [
        for (final m in cur2.messages)
          if (m.id == tmpId) m.copyWith(status: MessageStatus.failed) else m,
      ];
      state = AsyncValue.data(cur2.copyWith(messages: replaced));
    }
  }

  /// Debounced typing signal — the composer calls this on keystroke change.
  void setTyping(bool typing) {
    ref.read(wsClientProvider).sendTyping(arg, typing);
  }
}

final conversationControllerProvider = AsyncNotifierProvider.family<
    ConversationController, ConversationScreenState, String>(
  ConversationController.new,
);
