import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Interface so tests can swap an in-memory implementation.
abstract class SecureAuthStorage {
  factory SecureAuthStorage({FlutterSecureStorage? storage}) =
      _SecureAuthStorageImpl;

  Future<String?> readAccess();
  Future<String?> readRefresh();
  Future<String?> readUserJson();
  Future<void> writeTokens({required String access, required String refresh});
  Future<void> writeUserJson(String json);
  Future<void> clear();
}

class _SecureAuthStorageImpl implements SecureAuthStorage {
  _SecureAuthStorageImpl({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _kAccess = 'auth.access';
  static const _kRefresh = 'auth.refresh';
  static const _kUserJson = 'auth.user_json';

  @override
  Future<String?> readAccess() => _storage.read(key: _kAccess);
  @override
  Future<String?> readRefresh() => _storage.read(key: _kRefresh);
  @override
  Future<String?> readUserJson() => _storage.read(key: _kUserJson);

  @override
  Future<void> writeTokens({
    required String access,
    required String refresh,
  }) async {
    await _storage.write(key: _kAccess, value: access);
    await _storage.write(key: _kRefresh, value: refresh);
  }

  @override
  Future<void> writeUserJson(String json) =>
      _storage.write(key: _kUserJson, value: json);

  @override
  Future<void> clear() async {
    await _storage.delete(key: _kAccess);
    await _storage.delete(key: _kRefresh);
    await _storage.delete(key: _kUserJson);
  }
}
