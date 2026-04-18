/// DTO mirrors. Strictly ciphertext fields — **no plaintext/text/body/content
/// field is ever added here** (ADR-0013). The widget tree receives plaintext
/// only via the decrypted [MessageView] in `domain/`.

class PeerKeyDto {
  const PeerKeyDto({
    required this.id,
    required this.publicKey,
    required this.keyVersion,
  });
  final String id;
  final String publicKey;
  final int keyVersion;

  factory PeerKeyDto.fromJson(Map<String, dynamic> json) => PeerKeyDto(
        id: json['id'] as String,
        publicKey: json['public_key'] as String,
        keyVersion: (json['key_version'] as num?)?.toInt() ?? 1,
      );
}

class ConversationDto {
  const ConversationDto({
    required this.id,
    required this.participantIds,
    required this.lastMessageAt,
    required this.unreadCount,
    this.lastMessagePreviewSender,
  });

  final String id;
  final List<String> participantIds;
  final DateTime? lastMessageAt;
  final int unreadCount;
  final String? lastMessagePreviewSender;

  factory ConversationDto.fromJson(Map<String, dynamic> json) =>
      ConversationDto(
        id: json['id'] as String,
        participantIds:
            ((json['participant_ids'] as List?) ?? const []).cast<String>(),
        lastMessageAt: json['last_message_at'] != null
            ? DateTime.tryParse(json['last_message_at'] as String)
            : null,
        unreadCount: (json['unread_count'] as num?)?.toInt() ?? 0,
        lastMessagePreviewSender: json['last_message_sender_id'] as String?,
      );
}

/// Ciphertext envelope — the ONLY shape of messages on the wire. No plaintext
/// field exists on this class; adding one would fail the Phase 6 Pydantic
/// `extra="forbid"` on the server anyway.
class MessageEnvelopeDto {
  const MessageEnvelopeDto({
    required this.id,
    required this.conversationId,
    required this.senderId,
    required this.ciphertext,
    required this.nonce,
    required this.ephemeralPublicKey,
    required this.recipientKeyId,
    required this.sentAt,
    this.readAt,
  });

  final String id;
  final String conversationId;
  final String senderId;
  final String ciphertext;
  final String nonce;
  final String ephemeralPublicKey;
  final String recipientKeyId;
  final DateTime sentAt;
  final DateTime? readAt;

  factory MessageEnvelopeDto.fromJson(Map<String, dynamic> json) =>
      MessageEnvelopeDto(
        id: json['id'] as String,
        conversationId: json['conversation_id'] as String,
        senderId: json['sender_id'] as String,
        ciphertext: json['ciphertext'] as String,
        nonce: json['nonce'] as String,
        ephemeralPublicKey: json['ephemeral_public_key'] as String,
        recipientKeyId: json['recipient_key_id'] as String,
        sentAt: DateTime.parse(json['sent_at'] as String),
        readAt: json['read_at'] != null
            ? DateTime.tryParse(json['read_at'] as String)
            : null,
      );

  /// Outbound send-shape — strictly ciphertext. Widget tree calls into the
  /// controller with `String plaintext`; the controller encrypts and wraps.
  Map<String, dynamic> toSendJson() => {
        'ciphertext': ciphertext,
        'nonce': nonce,
        'ephemeral_public_key': ephemeralPublicKey,
        'recipient_key_id': recipientKeyId,
      };
}
