import '../../../shared/widgets/chat_bubble.dart';

/// Plaintext-only view-model fed into ChatBubble. The only place in the app
/// that turns a ciphertext envelope into this shape is
/// [MessagingCryptoService.decryptWith] via the conversation controller.
class MessageView {
  const MessageView({
    required this.id,
    required this.text,
    required this.isMine,
    required this.sentAt,
    required this.status,
    this.readAt,
  });

  final String id;
  final String text;
  final bool isMine;
  final DateTime sentAt;
  final MessageStatus status;
  final DateTime? readAt;

  MessageView copyWith({
    String? id,
    String? text,
    bool? isMine,
    DateTime? sentAt,
    MessageStatus? status,
    DateTime? readAt,
  }) =>
      MessageView(
        id: id ?? this.id,
        text: text ?? this.text,
        isMine: isMine ?? this.isMine,
        sentAt: sentAt ?? this.sentAt,
        status: status ?? this.status,
        readAt: readAt ?? this.readAt,
      );
}

class ConversationView {
  const ConversationView({
    required this.id,
    required this.peerId,
    required this.peerDisplayName,
    this.lastMessageAt,
    this.lastMessagePreview,
    this.unreadCount = 0,
    this.peerHasKey = true,
  });

  final String id;
  final String peerId;
  final String peerDisplayName;
  final DateTime? lastMessageAt;
  final String? lastMessagePreview;
  final int unreadCount;
  final bool peerHasKey;

  ConversationView copyWith({
    DateTime? lastMessageAt,
    String? lastMessagePreview,
    int? unreadCount,
    bool? peerHasKey,
    String? peerDisplayName,
  }) =>
      ConversationView(
        id: id,
        peerId: peerId,
        peerDisplayName: peerDisplayName ?? this.peerDisplayName,
        lastMessageAt: lastMessageAt ?? this.lastMessageAt,
        lastMessagePreview: lastMessagePreview ?? this.lastMessagePreview,
        unreadCount: unreadCount ?? this.unreadCount,
        peerHasKey: peerHasKey ?? this.peerHasKey,
      );
}
