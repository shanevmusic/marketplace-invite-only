/// Builds the public, shareable invite URL for a token.
///
/// The base is supplied at compile time via:
///   --dart-define=INVITE_BASE_URL=https://example.com
///
/// When unset (e.g. local dev), we fall back to a marketplace deep link
/// which works on a phone with the app installed.
class InviteLink {
  const InviteLink._();

  static const String _base = String.fromEnvironment(
    'INVITE_BASE_URL',
    defaultValue: '',
  );

  /// Returns a sharable URL for the given invite [token].
  ///
  /// Examples:
  ///   INVITE_BASE_URL=https://my.app  →  https://my.app/invite/<token>
  ///   INVITE_BASE_URL=https://demo/...index.html#  →  https://demo/...index.html#/invite/<token>
  ///   (unset) → marketplace://invite/<token>
  static String forToken(String token) {
    if (_base.isEmpty) return 'marketplace://invite/$token';
    final base = _base.endsWith('/') ? _base.substring(0, _base.length - 1) : _base;
    return '$base/invite/$token';
  }

  /// Whether a real public URL is configured.
  static bool get hasPublicBase => _base.isNotEmpty;
}
