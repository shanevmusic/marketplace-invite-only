import 'package:dio/dio.dart';

import '../../../data/api/api_config.dart';
import 'auth_dtos.dart';

/// Low-level HTTP wrapper. Stateless: no token storage here. AuthRepository
/// owns tokens and injects them via the Dio interceptor built in
/// token_interceptor.dart.
class AuthApi {
  AuthApi({Dio? dio})
      : _dio = dio ??
            (Dio(BaseOptions(baseUrl: ApiConfig.baseUrl))
              ..options.persistentConnection = true);

  final Dio _dio;
  Dio get dio => _dio;

  Future<AuthResponse> signup(SignupRequest body) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/auth/signup',
        data: body.toJson(),
      );
      return AuthResponse.fromJson(res.data!);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  Future<AuthResponse> login(LoginRequest body) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/auth/login',
        data: body.toJson(),
      );
      return AuthResponse.fromJson(res.data!);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  Future<TokenPair> refresh(RefreshRequest body) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/auth/refresh',
        data: body.toJson(),
      );
      return TokenPair.fromJson(res.data!);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  Future<void> logout(String refreshToken) async {
    try {
      await _dio.post<void>(
        '/auth/logout',
        data: {'refresh_token': refreshToken},
      );
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  Future<MeResponse> getMe() async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/auth/me');
      return MeResponse.fromJson(res.data!);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  Future<InviteValidation> validateInvite(String token) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        '/invites/validate',
        queryParameters: {'token': token},
      );
      return InviteValidation.fromJson(res.data!);
    } on DioException catch (e) {
      throw _toException(e);
    }
  }

  AuthApiException _toException(DioException e) {
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
      }
    }
    if (e.type == DioExceptionType.connectionError ||
        e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.receiveTimeout ||
        e.type == DioExceptionType.sendTimeout) {
      code = 'NETWORK';
    }
    return AuthApiException(
      statusCode: status,
      code: code,
      message: message,
      detail: detail,
    );
  }
}
