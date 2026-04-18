import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Local persistence for the user's X25519 keypair(s). ADR-0013 — old
/// private keys are retained under `keys.v1.rotated.{keyId}` so historical
/// ciphertext can still decrypt after rotation.
class MessagingKeyStore {
  MessagingKeyStore({FlutterSecureStorage? storage})
      : _storage = storage ?? const FlutterSecureStorage();

  final FlutterSecureStorage _storage;

  static const _activeKey = 'keys.v1.active';
  static const _rotatedPrefix = 'keys.v1.rotated.';

  Future<StoredKeypair?> readActive() async {
    final raw = await _storage.read(key: _activeKey);
    if (raw == null) return null;
    return StoredKeypair.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<void> writeActive(StoredKeypair kp) async {
    await _storage.write(key: _activeKey, value: jsonEncode(kp.toJson()));
  }

  Future<StoredKeypair?> readByKeyId(String keyId) async {
    final active = await readActive();
    if (active != null && active.keyId == keyId) return active;
    final raw = await _storage.read(key: '$_rotatedPrefix$keyId');
    if (raw == null) return null;
    return StoredKeypair.fromJson(jsonDecode(raw) as Map<String, dynamic>);
  }

  Future<void> rotateActiveTo(StoredKeypair next) async {
    final prev = await readActive();
    if (prev != null) {
      await _storage.write(
        key: '$_rotatedPrefix${prev.keyId}',
        value: jsonEncode(prev.toJson()),
      );
    }
    await writeActive(next);
  }

  Future<void> clear() async {
    await _storage.delete(key: _activeKey);
  }
}

class StoredKeypair {
  const StoredKeypair({
    required this.keyId,
    required this.publicKey,
    required this.privateKey,
    required this.createdAt,
  });

  final String keyId;
  final Uint8List publicKey;
  final Uint8List privateKey;
  final DateTime createdAt;

  Map<String, dynamic> toJson() => {
        'key_id': keyId,
        'public_key': base64Encode(publicKey),
        'private_key': base64Encode(privateKey),
        'created_at': createdAt.toIso8601String(),
      };

  factory StoredKeypair.fromJson(Map<String, dynamic> json) => StoredKeypair(
        keyId: json['key_id'] as String,
        publicKey: Uint8List.fromList(
          base64Decode(json['public_key'] as String),
        ),
        privateKey: Uint8List.fromList(
          base64Decode(json['private_key'] as String),
        ),
        createdAt: DateTime.parse(json['created_at'] as String),
      );
}
