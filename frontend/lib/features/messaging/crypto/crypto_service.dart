import 'dart:convert';
import 'dart:typed_data';

import 'package:crypto/crypto.dart' as pcrypto;
import 'package:cryptography/cryptography.dart';

/// X25519 + AES-256-GCM crypto service. Plaintext strings in, base64
/// ciphertext + nonce + ephemeral pubkey out — and vice versa. The only
/// place in the app where a String plaintext is converted to/from the opaque
/// envelope fields that hit the network. ADR-0009 / ADR-0013.
class MessagingCryptoService {
  MessagingCryptoService({X25519? x25519, AesGcm? aes})
      : _x25519 = x25519 ?? X25519(),
        _aes = aes ?? AesGcm.with256bits();

  final X25519 _x25519;
  final AesGcm _aes;

  Future<CryptoKeyPair> generateKeypair() async {
    final kp = await _x25519.newKeyPair();
    final pub = await kp.extractPublicKey();
    final priv = await kp.extractPrivateKeyBytes();
    return CryptoKeyPair(
      publicKey: Uint8List.fromList(pub.bytes),
      privateKey: Uint8List.fromList(priv),
    );
  }

  /// Encrypts `plaintext` for the peer whose X25519 public key is `peerPublicKey`.
  /// Ephemeral ECDH per message — the `ephemeralPublicKey` in the envelope is
  /// the freshly generated sender-side pubkey for this message only.
  Future<EncryptedEnvelope> encryptFor({
    required Uint8List peerPublicKey,
    required String plaintext,
  }) async {
    final ephemeral = await _x25519.newKeyPair();
    final ephemeralPub = await ephemeral.extractPublicKey();
    final shared = await _x25519.sharedSecretKey(
      keyPair: ephemeral,
      remotePublicKey: SimplePublicKey(peerPublicKey, type: KeyPairType.x25519),
    );
    final keyBytes = await shared.extractBytes();
    final aesKey = SecretKey(_hkdf(keyBytes, salt: ephemeralPub.bytes));
    final secretBox = await _aes.encryptString(plaintext, secretKey: aesKey);
    return EncryptedEnvelope(
      ciphertext: base64Encode(
        Uint8List.fromList([...secretBox.cipherText, ...secretBox.mac.bytes]),
      ),
      nonce: base64Encode(secretBox.nonce),
      ephemeralPublicKey: base64Encode(ephemeralPub.bytes),
    );
  }

  /// Decrypts an inbound envelope. `privateKey` is the recipient's private
  /// bytes for the `recipientKeyId` the sender targeted.
  Future<String> decryptWith({
    required Uint8List privateKey,
    required String ciphertextB64,
    required String nonceB64,
    required String ephemeralPublicKeyB64,
  }) async {
    final ct = base64Decode(ciphertextB64);
    final nonce = base64Decode(nonceB64);
    final ephPub = base64Decode(ephemeralPublicKeyB64);
    // Last 16 bytes of ct = GCM tag.
    if (ct.length < 16) {
      throw const FormatException('ciphertext too short');
    }
    final cipherOnly = ct.sublist(0, ct.length - 16);
    final macBytes = ct.sublist(ct.length - 16);

    final kp = await _x25519.newKeyPairFromSeed(privateKey);
    final shared = await _x25519.sharedSecretKey(
      keyPair: kp,
      remotePublicKey: SimplePublicKey(ephPub, type: KeyPairType.x25519),
    );
    final keyBytes = await shared.extractBytes();
    final aesKey = SecretKey(_hkdf(keyBytes, salt: ephPub));
    final box = SecretBox(cipherOnly, nonce: nonce, mac: Mac(macBytes));
    return _aes.decryptString(box, secretKey: aesKey);
  }

  /// Safety number: 12 hex chars of SHA-256 over the sorted pair of pubkeys.
  String safetyNumber(Uint8List a, Uint8List b) {
    final pair = _sortedPair(a, b);
    final prefix = utf8.encode('marketplace-v1');
    final digest = pcrypto.sha256.convert([...prefix, ...pair.$1, ...pair.$2]);
    final hex = digest.toString().substring(0, 12).toUpperCase();
    return '${hex.substring(0, 4)} ${hex.substring(4, 8)} ${hex.substring(8, 12)}';
  }

  (List<int>, List<int>) _sortedPair(Uint8List a, Uint8List b) {
    for (var i = 0; i < a.length && i < b.length; i++) {
      if (a[i] < b[i]) return (a.toList(), b.toList());
      if (a[i] > b[i]) return (b.toList(), a.toList());
    }
    return (a.toList(), b.toList());
  }

  /// Minimal HKDF-lite: SHA-256(salt || ikm)[0..32]. Good enough for v1 —
  /// ADR-0009 documents that the scheme is not Signal-grade.
  List<int> _hkdf(List<int> ikm, {required List<int> salt}) {
    final digest = pcrypto.sha256.convert([...salt, ...ikm]);
    return digest.bytes.sublist(0, 32);
  }
}

class CryptoKeyPair {
  const CryptoKeyPair({required this.publicKey, required this.privateKey});
  final Uint8List publicKey;
  final Uint8List privateKey;
}

class EncryptedEnvelope {
  const EncryptedEnvelope({
    required this.ciphertext,
    required this.nonce,
    required this.ephemeralPublicKey,
  });
  final String ciphertext;
  final String nonce;
  final String ephemeralPublicKey;
}
