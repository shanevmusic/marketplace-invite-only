/// Raw inbound WS envelope. Feature controllers subscribe to typed streams
/// via [RealtimeDispatcher]; this is the low-level shape.
class WsEvent {
  const WsEvent({
    required this.type,
    required this.channel,
    required this.data,
  });

  final String type;
  final String channel;
  final Map<String, dynamic> data;

  factory WsEvent.fromJson(Map<String, dynamic> json) => WsEvent(
        type: (json['type'] as String?) ?? 'unknown',
        channel: (json['channel'] as String?) ?? '',
        data: (json['data'] as Map?)?.cast<String, dynamic>() ?? const {},
      );
}

/// Messaging-scoped event variants. All carry decrypted-by-controller state —
/// the widget tree never sees ciphertext (ADR-0013).
sealed class MessagingEvent {
  const MessagingEvent(this.conversationId);
  final String conversationId;
}

class MessageNewEvent extends MessagingEvent {
  const MessageNewEvent({
    required String conversationId,
    required this.messageId,
    required this.senderId,
    required this.ciphertext,
    required this.nonce,
    required this.ephemeralPublicKey,
    required this.recipientKeyId,
    required this.sentAt,
  }) : super(conversationId);
  final String messageId;
  final String senderId;
  final String ciphertext;
  final String nonce;
  final String ephemeralPublicKey;
  final String recipientKeyId;
  final DateTime sentAt;
}

class MessageReadEvent extends MessagingEvent {
  const MessageReadEvent({
    required String conversationId,
    required this.messageId,
    required this.readerId,
    required this.readAt,
  }) : super(conversationId);
  final String messageId;
  final String readerId;
  final DateTime readAt;
}

class TypingEvent extends MessagingEvent {
  const TypingEvent({
    required String conversationId,
    required this.userId,
    required this.isTyping,
  }) : super(conversationId);
  final String userId;
  final bool isTyping;
}

/// Customer-safe tracking subset: no coords, ever. ADR-0014.
sealed class TrackingEvent {
  const TrackingEvent(this.deliveryOrderId);
  final String deliveryOrderId;
}

class DeliveryStatusEvent extends TrackingEvent {
  const DeliveryStatusEvent({
    required String deliveryOrderId,
    required this.status,
    required this.changedAt,
  }) : super(deliveryOrderId);
  final String status;
  final DateTime changedAt;
}

class DeliveryEtaEvent extends TrackingEvent {
  const DeliveryEtaEvent({
    required String deliveryOrderId,
    required this.etaSeconds,
    required this.etaUpdatedAt,
  }) : super(deliveryOrderId);
  final int? etaSeconds;
  final DateTime etaUpdatedAt;
}

/// Internal tracking superset. Never imported from customer/** — enforced by
/// the ADR-0014 import-boundary test.
sealed class InternalTrackingEvent extends TrackingEvent {
  const InternalTrackingEvent(super.id);
}

class DeliveryLocationEvent extends InternalTrackingEvent {
  const DeliveryLocationEvent({
    required String deliveryOrderId,
    required this.deliveryLat,
    required this.deliveryLng,
    required this.recordedAt,
  }) : super(deliveryOrderId);
  final double deliveryLat;
  final double deliveryLng;
  final DateTime recordedAt;
}

class InternalDeliveryStatusEvent extends InternalTrackingEvent {
  const InternalDeliveryStatusEvent({
    required String deliveryOrderId,
    required this.status,
    required this.changedAt,
  }) : super(deliveryOrderId);
  final String status;
  final DateTime changedAt;
}

class InternalDeliveryEtaEvent extends InternalTrackingEvent {
  const InternalDeliveryEtaEvent({
    required String deliveryOrderId,
    required this.etaSeconds,
    required this.etaUpdatedAt,
  }) : super(deliveryOrderId);
  final int? etaSeconds;
  final DateTime etaUpdatedAt;
}

/// Signals that the server refused a subscription with `channel.forbidden`.
class SubscriptionDeniedEvent {
  const SubscriptionDeniedEvent(this.channel);
  final String channel;
}
