import 'dart:convert';

import 'package:dio/dio.dart';

import '../../../data/api/api_config.dart';
import 'auth_api.dart';
import 'auth_dtos.dart';
import 'secure_storage.dart';
import 'token_interceptor.dart';

/// Session object: a flattened view the UI reads without knowing DTO shapes.
class AuthSession {
  const AuthSession({
    required this.user,
    required this.accessToken,
    required this.refreshToken,
  });

  final AuthUser user;
  final String accessToken;
  final String refreshToken;

  AuthSession copyWith({
    AuthUser? user,
    String? accessToken,
    String? refreshToken,
  }) =>
      AuthSession(
        user: user ?? this.user,
        accessToken: accessToken ?? this.accessToken,
        refreshToken: refreshToken ?? this.refreshToken,
      );
}

/// Wraps AuthApi + secure storage and owns in-memory session state. The
/// AuthController (Riverpod AsyncNotifier) is the only caller of this class.
///
/// Exposes:
///   - login / signup / logout / refresh
///   - seedFromStorage (boot path)
///   - sessionExpired Stream via onSessionExpired callback
class AuthRepository {
  AuthRepository({AuthApi? api, SecureAuthStorage? storage, Dio? dio})
      : _storage = storage ?? SecureAuthStorage(),
        _dio = dio ?? Dio(BaseOptions(baseUrl: ApiConfig.baseUrl)) {
    _api = api ?? AuthApi(dio: _dio);
    _dio.interceptors.add(
      TokenInterceptor(
        readAccess: () => _session?.accessToken,
        readRefresh: () => _session?.refreshToken,
        onRefresh: _refreshInternal,
        onSessionExpired: _fireSessionExpired,
        retryDio: _dio,
      ),
    );
  }

  final Dio _dio;
  late final AuthApi _api;
  final SecureAuthStorage _storage;

  AuthSession? _session;
  void Function()? _onSessionExpired;

  AuthSession? get currentSession => _session;
  AuthApi get api => _api;

  void setSessionExpiredListener(void Function() cb) {
    _onSessionExpired = cb;
  }

  void _fireSessionExpired() {
    _session = null;
    // fire-and-forget — storage clear is awaited by the controller.
    _storage.clear();
    _onSessionExpired?.call();
  }

  Future<AuthSession> login(LoginRequest body) async {
    final res = await _api.login(body);
    final session = _sessionFromResponse(res);
    await _persist(session);
    _session = session;
    return session;
  }

  Future<AuthSession> signup(SignupRequest body) async {
    final res = await _api.signup(body);
    final session = _sessionFromResponse(res);
    await _persist(session);
    _session = session;
    return session;
  }

  Future<void> logout() async {
    final refresh = _session?.refreshToken;
    _session = null;
    await _storage.clear();
    if (refresh != null) {
      try {
        await _api.logout(refresh);
      } catch (_) {
        // fire-and-forget — device state is source of truth.
      }
    }
  }

  /// Refreshes tokens using the stored refresh token. Returns the new access
  /// token. Throws AuthApiException on failure (caller should treat as
  /// session expiration).
  Future<String> _refreshInternal() async {
    final refresh = _session?.refreshToken;
    if (refresh == null) {
      throw AuthApiException(
        statusCode: 401,
        code: 'TOKEN_INVALID',
        message: 'no refresh token',
      );
    }
    final pair = await _api.refresh(RefreshRequest(refreshToken: refresh));
    _session = _session!.copyWith(
      accessToken: pair.accessToken,
      refreshToken: pair.refreshToken,
    );
    await _storage.writeTokens(
      access: pair.accessToken,
      refresh: pair.refreshToken,
    );
    return pair.accessToken;
  }

  /// Public wrapper used by the controller on cold-start / explicit refresh.
  Future<AuthSession> refresh() async {
    await _refreshInternal();
    final me = await _api.getMe();
    final updated = _session!.copyWith(user: me.toAuthUser());
    _session = updated;
    await _storage.writeUserJson(jsonEncode(updated.user.toJson()));
    return updated;
  }

  Future<AuthSession?> seedFromStorage() async {
    final access = await _storage.readAccess();
    final refresh = await _storage.readRefresh();
    final userJson = await _storage.readUserJson();
    if (access == null || refresh == null || userJson == null) {
      return null;
    }
    try {
      final user = AuthUser.fromJson(
        jsonDecode(userJson) as Map<String, dynamic>,
      );
      _session = AuthSession(
        user: user,
        accessToken: access,
        refreshToken: refresh,
      );
      return _session;
    } catch (_) {
      await _storage.clear();
      return null;
    }
  }

  Future<MeResponse> getCurrentUser() => _api.getMe();

  String? currentAccessToken() => _session?.accessToken;

  Future<InviteValidation> validateInvite(String token) =>
      _api.validateInvite(token);

  AuthSession _sessionFromResponse(AuthResponse res) => AuthSession(
        user: res.user,
        accessToken: res.accessToken,
        refreshToken: res.refreshToken,
      );

  Future<void> _persist(AuthSession session) async {
    await _storage.writeTokens(
      access: session.accessToken,
      refresh: session.refreshToken,
    );
    await _storage.writeUserJson(jsonEncode(session.user.toJson()));
  }
}
