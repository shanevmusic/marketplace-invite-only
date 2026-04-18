import 'package:dio/dio.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/features/auth/data/auth_api.dart';
import 'package:marketplace/features/auth/data/auth_dtos.dart';
import 'package:marketplace/features/auth/data/auth_repository.dart';
import 'package:marketplace/features/auth/data/secure_storage.dart';

class MockAuthApi extends Mock implements AuthApi {}

class FakeSignupRequest extends Fake implements SignupRequest {}

class FakeLoginRequest extends Fake implements LoginRequest {}

class FakeRefreshRequest extends Fake implements RefreshRequest {}

void registerFallbackValues() {
  registerFallbackValue(FakeSignupRequest());
  registerFallbackValue(FakeLoginRequest());
  registerFallbackValue(FakeRefreshRequest());
}

/// An [AuthRepository] subclass that replaces the real [AuthApi] with a mock
/// and uses an in-memory secure storage to keep tests hermetic.
class TestAuthRepository extends AuthRepository {
  TestAuthRepository({required MockAuthApi api, SecureAuthStorage? storage})
      : super(api: api, storage: storage ?? _InMemoryStorage(), dio: Dio());
}

class _InMemoryStorage implements SecureAuthStorage {
  final Map<String, String> _m = {};
  @override
  Future<void> clear() async {
    _m.clear();
  }

  @override
  Future<String?> readAccess() async => _m['access'];

  @override
  Future<String?> readRefresh() async => _m['refresh'];

  @override
  Future<String?> readUserJson() async => _m['user'];

  @override
  Future<void> writeTokens({required String access, required String refresh}) async {
    _m['access'] = access;
    _m['refresh'] = refresh;
  }

  @override
  Future<void> writeUserJson(String json) async {
    _m['user'] = json;
  }
}

AuthResponse sampleAuthResponse({String role = 'customer'}) => AuthResponse(
      accessToken: 'a.b.c',
      refreshToken: 'r.r.r',
      tokenType: 'Bearer',
      expiresIn: 900,
      user: AuthUser(
        id: '00000000-0000-0000-0000-000000000001',
        email: 'user@example.com',
        role: role,
        displayName: 'Test User',
      ),
    );
