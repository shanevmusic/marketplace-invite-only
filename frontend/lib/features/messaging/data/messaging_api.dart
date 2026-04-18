import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import 'messaging_dtos.dart';

class MessagingApi {
  MessagingApi(this._dio);
  final Dio _dio;

  Future<PeerKeyDto> registerKey({
    required String publicKeyBase64,
    int keyVersion = 1,
  }) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/keys',
        data: {'public_key': publicKeyBase64, 'key_version': keyVersion},
      );
      return PeerKeyDto.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<PeerKeyDto?> getPeerKey(String userId) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/keys/$userId');
      return PeerKeyDto.fromJson(r.data!);
    } on DioException catch (e) {
      final ex = ApiException.fromDio(e);
      if (ex.isNotFound) return null;
      throw ex;
    }
  }

  Future<List<ConversationDto>> listConversations() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/conversations');
      final items = (r.data?['items'] as List?) ?? const [];
      return items
          .map((e) =>
              ConversationDto.fromJson((e as Map).cast<String, dynamic>()))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ConversationDto> createOrGet(String peerId) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/conversations',
        data: {'participant_id': peerId},
      );
      return ConversationDto.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<MessageEnvelopeDto>> listMessages(
    String conversationId, {
    int limit = 50,
  }) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/conversations/$conversationId/messages',
        queryParameters: {'limit': limit, 'direction': 'desc'},
      );
      final items = (r.data?['items'] as List?) ?? const [];
      return items
          .map((e) =>
              MessageEnvelopeDto.fromJson((e as Map).cast<String, dynamic>()))
          .toList();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<MessageEnvelopeDto> sendMessage(
    String conversationId,
    MessageEnvelopeDto envelope,
  ) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/conversations/$conversationId/messages',
        data: envelope.toSendJson(),
      );
      return MessageEnvelopeDto.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> markRead(String conversationId, String messageId) async {
    try {
      await _dio.post<Map<String, dynamic>>(
        '/conversations/$conversationId/messages/$messageId/read',
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

final messagingApiProvider = Provider<MessagingApi>((ref) {
  return MessagingApi(ref.watch(apiClientProvider));
});
