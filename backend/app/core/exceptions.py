"""Domain exceptions mapped to HTTP status codes and error-envelope codes.

Every exception raised from services is a subclass of ``AppException``.
The global handler in ``app.main`` converts them to the standard error
envelope:

    {"error": {"code": "...", "message": "...", "detail": null}}
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base exception for all application-layer errors."""

    http_status: int = 400
    code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        details: Any = None,
        code: str | None = None,
        http_status: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status


# ---------------------------------------------------------------------------
# Generic HTTP exceptions
# ---------------------------------------------------------------------------


class AuthenticationError(AppException):
    """401 — Missing, invalid, or expired authentication token."""

    http_status = 401
    code = "AUTH_TOKEN_INVALID"


class AuthorizationError(AppException):
    """403 — Authenticated but role insufficient."""

    http_status = 403
    code = "PERMISSION_DENIED"


class NotFoundError(AppException):
    """404 — Resource does not exist or is visibility-hidden."""

    http_status = 404
    code = "NOT_FOUND"


class ConflictError(AppException):
    """409 — Duplicate or state-conflict error."""

    http_status = 409
    code = "CONFLICT"


class ValidationError(AppException):
    """422 — Request body failed validation."""

    http_status = 422
    code = "VALIDATION_FAILED"


class RateLimitError(AppException):
    """429 — Too many requests."""

    http_status = 429
    code = "RATE_LIMITED"


# ---------------------------------------------------------------------------
# Auth domain exceptions
# ---------------------------------------------------------------------------


class InvalidCredentials(AuthenticationError):
    """Wrong email or password."""

    code = "AUTH_INVALID_CREDENTIALS"

    def __init__(self, message: str = "Invalid email or password.") -> None:
        super().__init__(message)


class TokenRevoked(AuthenticationError):
    """Refresh token has been explicitly revoked."""

    code = "AUTH_TOKEN_REVOKED"

    def __init__(self, message: str = "Token has been revoked.") -> None:
        super().__init__(message)


class TokenReused(AuthenticationError):
    """A rotated (already-consumed) refresh token was presented — possible theft."""

    code = "AUTH_TOKEN_REUSED"

    def __init__(
        self,
        message: str = "Refresh token reuse detected; all sessions revoked.",
    ) -> None:
        super().__init__(message)


class TokenExpired(AuthenticationError):
    """Access or refresh token is past its expiry."""

    code = "AUTH_TOKEN_EXPIRED"

    def __init__(self, message: str = "Token has expired.") -> None:
        super().__init__(message)


class InvalidTokenError(AuthenticationError):
    """Malformed or signature-invalid token."""

    code = "AUTH_TOKEN_INVALID"

    def __init__(self, message: str = "Token is invalid.") -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Invite domain exceptions
# ---------------------------------------------------------------------------


class InviteInvalid(AppException):
    """Generic invalid invite (token not found)."""

    http_status = 400
    code = "INVITE_INVALID"

    def __init__(self, message: str = "Invite token is invalid.") -> None:
        super().__init__(message)


class InviteExpired(AppException):
    """Invite token past its expiry date."""

    http_status = 400
    code = "INVITE_EXPIRED"

    def __init__(self, message: str = "Invite token has expired.") -> None:
        super().__init__(message)


class InviteAlreadyUsed(AppException):
    """Single-use invite already consumed."""

    http_status = 409
    code = "INVITE_USED"

    def __init__(self, message: str = "Invite token has already been used.") -> None:
        super().__init__(message)


class InviteRevoked(AppException):
    """Invite was explicitly revoked."""

    http_status = 400
    code = "INVITE_REVOKED"

    def __init__(self, message: str = "Invite token has been revoked.") -> None:
        super().__init__(message)


class InviteRoleMismatch(AppException):
    """Chosen role does not match the invite's role_target."""

    http_status = 400
    code = "INVITE_ROLE_MISMATCH"

    def __init__(
        self,
        message: str = "Chosen role does not match the invite's target role.",
    ) -> None:
        super().__init__(message)


class EmailTaken(ConflictError):
    """Email address already registered."""

    code = "EMAIL_TAKEN"

    def __init__(self, message: str = "Email address is already registered.") -> None:
        super().__init__(message)
