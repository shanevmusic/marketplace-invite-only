import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';

// ---------------------------------------------------------------------------
// DTOs
// ---------------------------------------------------------------------------

class PatchMeRequest {
  const PatchMeRequest({
    this.displayName,
    this.phone,
    this.avatarUrl,
  });

  final String? displayName;
  final String? phone;
  final String? avatarUrl;

  Map<String, dynamic> toJson() => {
        if (displayName != null) 'display_name': displayName,
        if (phone != null) 'phone': phone,
        if (avatarUrl != null) 'avatar_url': avatarUrl,
      };
}

class ChangePasswordRequest {
  const ChangePasswordRequest({
    required this.currentPassword,
    required this.newPassword,
  });

  final String currentPassword;
  final String newPassword;

  Map<String, dynamic> toJson() => {
        'current_password': currentPassword,
        'new_password': newPassword,
      };
}

class NotificationPrefs {
  const NotificationPrefs({
    required this.pushEnabled,
    required this.emailEnabled,
    required this.orderUpdates,
    required this.messages,
    required this.marketing,
  });

  final bool pushEnabled;
  final bool emailEnabled;
  final bool orderUpdates;
  final bool messages;
  final bool marketing;

  factory NotificationPrefs.fromJson(Map<String, dynamic> json) =>
      NotificationPrefs(
        pushEnabled: (json['push_enabled'] as bool?) ?? false,
        emailEnabled: (json['email_enabled'] as bool?) ?? false,
        orderUpdates: (json['order_updates'] as bool?) ?? false,
        messages: (json['messages'] as bool?) ?? false,
        marketing: (json['marketing'] as bool?) ?? false,
      );

  Map<String, dynamic> toJson() => {
        'push_enabled': pushEnabled,
        'email_enabled': emailEnabled,
        'order_updates': orderUpdates,
        'messages': messages,
        'marketing': marketing,
      };

  NotificationPrefs copyWith({
    bool? pushEnabled,
    bool? emailEnabled,
    bool? orderUpdates,
    bool? messages,
    bool? marketing,
  }) =>
      NotificationPrefs(
        pushEnabled: pushEnabled ?? this.pushEnabled,
        emailEnabled: emailEnabled ?? this.emailEnabled,
        orderUpdates: orderUpdates ?? this.orderUpdates,
        messages: messages ?? this.messages,
        marketing: marketing ?? this.marketing,
      );
}

// ---------------------------------------------------------------------------
// API class
// ---------------------------------------------------------------------------

class SettingsApi {
  SettingsApi(this._dio);
  final Dio _dio;

  /// PATCH /api/v1/auth/me
  Future<Map<String, dynamic>> patchMe(PatchMeRequest body) async {
    try {
      final r = await _dio.patch<Map<String, dynamic>>(
        '/auth/me',
        data: body.toJson(),
      );
      return r.data!;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// POST /api/v1/auth/me/password
  /// Returns normally on 204. Throws ApiException on 400 (wrong current pw).
  Future<void> changePassword(ChangePasswordRequest body) async {
    try {
      await _dio.post<void>(
        '/auth/me/password',
        data: body.toJson(),
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// GET /api/v1/auth/me/notifications
  Future<NotificationPrefs> getNotificationPrefs() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/auth/me/notifications',
      );
      return NotificationPrefs.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// PATCH /api/v1/auth/me/notifications
  Future<NotificationPrefs> patchNotificationPrefs(
    Map<String, dynamic> body,
  ) async {
    try {
      final r = await _dio.patch<Map<String, dynamic>>(
        '/auth/me/notifications',
        data: body,
      );
      return NotificationPrefs.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

final settingsApiProvider = Provider<SettingsApi>((ref) {
  final dio = ref.watch(apiClientProvider);
  return SettingsApi(dio);
});
