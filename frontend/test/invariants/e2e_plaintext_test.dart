// ADR-0009: user message plaintext must NEVER leave the device. The wire
// payload emitted by MessageEnvelopeDto.toSendJson() must contain only
// ciphertext, nonce, ephemeral public key, and recipient key id.
import 'package:flutter_test/flutter_test.dart';
import 'package:marketplace/features/messaging/data/messaging_dtos.dart';

void main() {
  test('MessageEnvelopeDto.toSendJson has no plaintext field', () {
    const plaintext = 'the quick brown fox jumps over the lazy dog';
    final dto = MessageEnvelopeDto(
      id: 'tmp',
      conversationId: 'c1',
      senderId: 'me',
      recipientKeyId: 'k1',
      ciphertext: 'AAAA',
      nonce: 'BBBB',
      ephemeralPublicKey: 'CCCC',
      sentAt: DateTime.utc(2026, 1, 1),
    );
    final body = dto.toSendJson();
    final keys = body.keys.toSet();
    expect(keys, containsAll({'ciphertext', 'nonce', 'ephemeral_public_key'}));
    // Assert the body has no key that would leak plaintext.
    expect(keys.contains('text'), isFalse);
    expect(keys.contains('plaintext'), isFalse);
    expect(keys.contains('body'), isFalse);
    expect(keys.contains('message'), isFalse);
    // Assert the body's values do not accidentally include the plaintext.
    for (final v in body.values) {
      final s = v?.toString() ?? '';
      expect(s.contains(plaintext), isFalse,
          reason: 'wire payload leaked plaintext: $s');
    }
  });
}
