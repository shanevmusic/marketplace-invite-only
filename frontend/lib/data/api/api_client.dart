import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/state/auth_controller.dart';

/// Shared Dio client — reuses the AuthRepository's Dio so the
/// TokenInterceptor handles access/refresh across all features.
final apiClientProvider = Provider<Dio>((ref) {
  final repo = ref.watch(authRepositoryProvider);
  return repo.api.dio;
});

/// Maps Dio errors to a simple ApiException with error code + status.
class ApiException implements Exception {
  ApiException({
    required this.statusCode,
    required this.code,
    this.message,
    this.detail,
  });

  final int statusCode;
  final String code;
  final String? message;
  final Object? detail;

  bool get isNetwork => code == 'NETWORK';
  bool get isNotFound => statusCode == 404;
  bool get isForbidden => statusCode == 403;
  bool get isConflict => statusCode == 409;
  bool get isRateLimited => statusCode == 429;
  bool get isUnauthorized => statusCode == 401;
  bool get isDeliveryAlreadyStarted => code == 'DELIVERY_ALREADY_STARTED';
  bool get isInsufficientStock => code == 'INSUFFICIENT_STOCK';
  bool get isStoreAlreadyExists => code == 'STORE_ALREADY_EXISTS';

  @override
  String toString() => 'ApiException($statusCode, $code, $message)';

  static ApiException fromDio(DioException e) {
    final status = e.response?.statusCode ?? 0;
    final data = e.response?.data;
    String code = 'UNKNOWN';
    String? message;
    Object? detail;
    if (data is Map) {
      final err = data['error'];
      if (err is Map) {
        code = (err['code'] as String?) ?? code;
        message = err['message'] as String?;
        detail = err['detail'];
      } else if (data['detail'] != null) {
        detail = data['detail'];
      }
    }
    if (e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout) {
      code = 'NETWORK';
    }
    return ApiException(
      statusCode: status,
      code: code,
      message: message,
      detail: detail,
    );
  }
}
