// API base URL resolution. Read from --dart-define at build time; defaults to
// the local FastAPI dev server. No secrets are embedded — the base URL is not
// a secret.
class ApiConfig {
  const ApiConfig._();

  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000/api/v1',
  );

  static const String deepLinkDomain = String.fromEnvironment(
    'DEEP_LINK_DOMAIN',
    defaultValue: 'marketplace.example.com',
  );

  static const String customScheme = 'marketplace';
}
