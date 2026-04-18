// ADR-0009: X25519 + AES-256-GCM round-trip, and the safety number is a
// deterministic function of the two public keys. Tests run without network.
import 'package:flutter_test/flutter_test.dart';
import 'package:marketplace/features/messaging/crypto/crypto_service.dart';

void main() {
  test('encrypt/decrypt round-trip', () async {
    final svc = MessagingCryptoService();
    final bob = await svc.generateKeypair();
    const plaintext = 'hello bob, it is alice';

    final envelope = await svc.encryptFor(
      peerPublicKey: bob.publicKey,
      plaintext: plaintext,
    );
    final decoded = await svc.decryptWith(
      privateKey: bob.privateKey,
      ciphertextB64: envelope.ciphertext,
      nonceB64: envelope.nonce,
      ephemeralPublicKeyB64: envelope.ephemeralPublicKey,
    );
    expect(decoded, plaintext);
  });

  test('safety number is deterministic and symmetric', () async {
    final svc = MessagingCryptoService();
    final a = await svc.generateKeypair();
    final b = await svc.generateKeypair();
    final n1 = svc.safetyNumber(a.publicKey, b.publicKey);
    final n2 = svc.safetyNumber(b.publicKey, a.publicKey);
    expect(n1, n2);
    final stripped = n1.replaceAll(' ', '');
    expect(stripped.length, 12);
    expect(RegExp(r'^[0-9A-F]+$').hasMatch(stripped), isTrue);
  });

  test('safety number differs between key pairs', () async {
    final svc = MessagingCryptoService();
    final a = await svc.generateKeypair();
    final b = await svc.generateKeypair();
    final c = await svc.generateKeypair();
    expect(svc.safetyNumber(a.publicKey, b.publicKey),
        isNot(svc.safetyNumber(a.publicKey, c.publicKey)));
  });
}
