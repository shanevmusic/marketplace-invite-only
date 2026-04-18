// Handwritten DTOs for Phase 8 — see docs/adr/0015-frontend-api-client.md.
// Shape matches backend/app/schemas/auth.py as of backend commit a649c58.

class SignupRequest {
  const SignupRequest({
    required this.inviteToken,
    required this.displayName,
    required this.email,
    required this.password,
    this.phone,
    this.roleChoice,
  });

  final String inviteToken;
  final String displayName;
  final String email;
  final String password;
  final String? phone;
  final String? roleChoice;

  Map<String, dynamic> toJson() => {
        'invite_token': inviteToken,
        'display_name': displayName,
        'email': email,
        'password': password,
        if (phone != null) 'phone': phone,
        if (roleChoice != null) 'role_choice': roleChoice,
      };
}

class LoginRequest {
  const LoginRequest({
    required this.email,
    required this.password,
    this.deviceLabel,
  });

  final String email;
  final String password;
  final String? deviceLabel;

  Map<String, dynamic> toJson() => {
        'email': email,
        'password': password,
        if (deviceLabel != null) 'device_label': deviceLabel,
      };
}

class RefreshRequest {
  const RefreshRequest({required this.refreshToken});
  final String refreshToken;
  Map<String, dynamic> toJson() => {'refresh_token': refreshToken};
}

class AuthUser {
  const AuthUser({
    required this.id,
    required this.email,
    required this.role,
    required this.displayName,
    this.referringSellerId,
  });

  final String id;
  final String email;
  final String role;
  final String displayName;
  final String? referringSellerId;

  factory AuthUser.fromJson(Map<String, dynamic> json) => AuthUser(
        id: json['id'] as String,
        email: json['email'] as String,
        role: json['role'] as String,
        displayName: json['display_name'] as String,
        referringSellerId: json['referring_seller_id'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'id': id,
        'email': email,
        'role': role,
        'display_name': displayName,
        if (referringSellerId != null) 'referring_seller_id': referringSellerId,
      };
}

class AuthResponse {
  const AuthResponse({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.expiresIn,
    required this.user,
  });

  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final int expiresIn;
  final AuthUser user;

  factory AuthResponse.fromJson(Map<String, dynamic> json) => AuthResponse(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
        tokenType: (json['token_type'] as String?) ?? 'Bearer',
        expiresIn: (json['expires_in'] as num?)?.toInt() ?? 900,
        user: AuthUser.fromJson(json['user'] as Map<String, dynamic>),
      );
}

class TokenPair {
  const TokenPair({
    required this.accessToken,
    required this.refreshToken,
    required this.expiresIn,
  });

  final String accessToken;
  final String refreshToken;
  final int expiresIn;

  factory TokenPair.fromJson(Map<String, dynamic> json) => TokenPair(
        accessToken: json['access_token'] as String,
        refreshToken: json['refresh_token'] as String,
        expiresIn: (json['expires_in'] as num?)?.toInt() ?? 900,
      );
}

class MeResponse {
  const MeResponse({
    required this.id,
    required this.email,
    required this.role,
    required this.displayName,
    this.phone,
    required this.isActive,
    this.referringSellerId,
  });

  final String id;
  final String email;
  final String role;
  final String displayName;
  final String? phone;
  final bool isActive;
  final String? referringSellerId;

  factory MeResponse.fromJson(Map<String, dynamic> json) => MeResponse(
        id: json['id'] as String,
        email: json['email'] as String,
        role: json['role'] as String,
        displayName: json['display_name'] as String,
        phone: json['phone'] as String?,
        isActive: (json['is_active'] as bool?) ?? true,
        referringSellerId: json['referring_seller_id'] as String?,
      );

  AuthUser toAuthUser() => AuthUser(
        id: id,
        email: email,
        role: role,
        displayName: displayName,
        referringSellerId: referringSellerId,
      );
}

class InviteValidation {
  const InviteValidation({
    required this.valid,
    this.role,
    this.inviterName,
    this.type,
    this.expiresAt,
  });

  final bool valid;
  final String? role;
  final String? inviterName;
  final String? type; // e.g. 'seller_referral' | 'admin_invite'
  final DateTime? expiresAt;

  factory InviteValidation.fromJson(Map<String, dynamic> json) =>
      InviteValidation(
        // Backend: {valid, type, role_target, issuer_display_name, issuer_role, ...}.
        // We also accept legacy {role, inviter_name, expires_at} for forward-compat.
        valid: json['valid'] as bool? ?? true,
        role: (json['role_target'] ?? json['role']) as String?,
        inviterName:
            (json['issuer_display_name'] ?? json['inviter_name']) as String?,
        type: json['type'] as String?,
        expiresAt: json['expires_at'] != null
            ? DateTime.tryParse(json['expires_at'] as String)
            : null,
      );

  /// Seller-referral invites surface role choice to the signup form.
  bool get roleChoiceRequired => type == 'seller_referral' || role == null;
}

/// Raised by AuthApi on failure. Maps machine-readable error codes; screens
/// translate to user-facing strings.
class AuthApiException implements Exception {
  AuthApiException({
    required this.statusCode,
    required this.code,
    this.message,
    this.detail,
  });

  final int statusCode;
  final String code;
  final String? message;
  final Object? detail;

  // Backend emits codes prefixed with 'AUTH_'. We accept the bare form too
  // for forward-compat (and our own client-raised 'NETWORK' sentinel).
  bool get isNetwork => code == 'NETWORK';
  bool get isUnauthorized => statusCode == 401;
  bool get isRateLimited => statusCode == 429;
  bool get isInvalidCredentials =>
      code == 'AUTH_INVALID_CREDENTIALS' || code == 'INVALID_CREDENTIALS';
  bool get isEmailTaken => code == 'AUTH_EMAIL_TAKEN' || code == 'EMAIL_TAKEN';
  bool get isTokenExpired =>
      code == 'AUTH_TOKEN_EXPIRED' ||
      code == 'AUTH_TOKEN_INVALID' ||
      code == 'TOKEN_EXPIRED' ||
      code == 'TOKEN_INVALID';

  @override
  String toString() => 'AuthApiException($statusCode, $code, $message)';
}
