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


class AccountSuspended(AuthorizationError):
    """403 — account is currently suspended by an admin."""

    code = "AUTH_ACCOUNT_SUSPENDED"

    def __init__(self, message: str = "Your account has been suspended.") -> None:
        super().__init__(message)


class UploadNotConfigured(AppException):
    """503 — S3 / object storage is not configured on the server."""

    http_status = 503
    code = "UPLOAD_NOT_CONFIGURED"

    def __init__(
        self,
        message: str = "Object storage is not configured on this server.",
    ) -> None:
        super().__init__(message)


class UploadInvalidContentType(ValidationError):
    """Unsupported content-type for an upload."""

    code = "UPLOAD_INVALID_CONTENT_TYPE"

    def __init__(self, message: str = "Unsupported content type.") -> None:
        super().__init__(message)


class UploadObjectMissing(ValidationError):
    """Confirm called on an object that does not exist or is oversized."""

    code = "UPLOAD_OBJECT_MISSING"

    def __init__(
        self, message: str = "Uploaded object is missing or invalid."
    ) -> None:
        super().__init__(message)


class PasswordTooCommon(ValidationError):
    """Password matches a known-common entry and was rejected."""

    code = "PASSWORD_TOO_COMMON"

    def __init__(
        self,
        message: str = "Password is too common; please choose a stronger password.",
    ) -> None:
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


# ---------------------------------------------------------------------------
# Seller / Store / Product domain exceptions (Phase 4)
# ---------------------------------------------------------------------------


class SellerProfileMissing(AppException):
    """User does not have a seller profile row."""

    http_status = 400
    code = "SELLER_PROFILE_MISSING"

    def __init__(
        self, message: str = "User does not have a seller profile."
    ) -> None:
        super().__init__(message)


class StoreAlreadyExists(ConflictError):
    """Seller already has a store (one-store-per-seller)."""

    code = "STORE_ALREADY_EXISTS"

    def __init__(self, message: str = "Seller already has a store.") -> None:
        super().__init__(message)


class StoreCityRequired(ValidationError):
    """City is required when creating a store."""

    code = "STORE_CITY_REQUIRED"

    def __init__(self, message: str = "City is required to create a store.") -> None:
        super().__init__(message)


class StoreNotFound(NotFoundError):
    """Store not found or visibility-hidden."""

    code = "STORE_NOT_FOUND"

    def __init__(self, message: str = "Store not found.") -> None:
        super().__init__(message)


class ProductNotFound(NotFoundError):
    """Product not found, deleted, or visibility-hidden."""

    code = "PRODUCT_NOT_FOUND"

    def __init__(self, message: str = "Product not found.") -> None:
        super().__init__(message)


class ProductOwnershipError(AuthorizationError):
    """Seller tried to mutate a product they don't own."""

    code = "PRODUCT_NOT_OWNED"

    def __init__(
        self, message: str = "You do not own this product."
    ) -> None:
        super().__init__(message)


class VisibilityDenied(NotFoundError):
    """Caller fails referral visibility scoping.

    Rendered as 404 to avoid leaking resource existence (see ADR-0007).
    """

    code = "NOT_FOUND"

    def __init__(self, message: str = "Resource not found.") -> None:
        super().__init__(message)


class SellerNotFound(NotFoundError):
    """Seller not found."""

    code = "SELLER_NOT_FOUND"

    def __init__(self, message: str = "Seller not found.") -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Order / fulfillment / retention domain exceptions (Phase 5)
# ---------------------------------------------------------------------------


class OrderNotFound(NotFoundError):
    """Order not found or visibility-hidden."""

    code = "ORDER_NOT_FOUND"

    def __init__(self, message: str = "Order not found.") -> None:
        super().__init__(message)


class OrderInvalidTransition(ConflictError):
    """Attempted state transition is not permitted."""

    code = "ORDER_INVALID_TRANSITION"

    def __init__(self, message: str = "Invalid order state transition.") -> None:
        super().__init__(message)


class OrderRetentionNotMet(ConflictError):
    """Hard-delete attempted before retention window elapsed."""

    code = "ORDER_RETENTION_NOT_MET"

    def __init__(
        self,
        message: str = "Order cannot be deleted before the retention period elapses.",
    ) -> None:
        super().__init__(message)


class DeliveryAlreadyStarted(ConflictError):
    """``out_for_delivery`` triggered twice."""

    code = "DELIVERY_ALREADY_STARTED"

    def __init__(self, message: str = "Delivery already started.") -> None:
        super().__init__(message)


class ProductOutOfStock(ConflictError):
    """Insufficient stock to satisfy a line item."""

    code = "PRODUCT_OUT_OF_STOCK"

    def __init__(self, message: str = "Product is out of stock.") -> None:
        super().__init__(message)


class ProductNotVisible(NotFoundError):
    """Customer placing an order referenced a product they can't see."""

    code = "PRODUCT_NOT_VISIBLE"

    def __init__(self, message: str = "Product is not available to you.") -> None:
        super().__init__(message)


class DriverNotRequested(ConflictError):
    """Admin tried to assign a driver to an order with no request row."""

    code = "DRIVER_NOT_REQUESTED"

    def __init__(
        self,
        message: str = "Seller has not requested a driver for this order.",
    ) -> None:
        super().__init__(message)


class DriverAlreadyAssigned(ConflictError):
    """Admin tried to assign a driver when one is already assigned."""

    code = "DRIVER_ALREADY_ASSIGNED"

    def __init__(
        self,
        message: str = "A driver has already been assigned to this order.",
    ) -> None:
        super().__init__(message)


class FulfillmentAlreadyChosen(ConflictError):
    """Seller tried to set fulfillment mode after one was already chosen."""

    code = "FULFILLMENT_ALREADY_CHOSEN"

    def __init__(
        self,
        message: str = "Fulfillment mode already chosen for this order.",
    ) -> None:
        super().__init__(message)


class RetentionSettingInvalid(ValidationError):
    """Invalid value for retention_min_days."""

    code = "RETENTION_SETTING_INVALID"

    def __init__(self, message: str = "retention_min_days must be >= 1.") -> None:
        super().__init__(message)


# ---------------------------------------------------------------------------
# Messaging domain exceptions (Phase 6)
# ---------------------------------------------------------------------------


class PublicKeyNotFound(NotFoundError):
    """No active public key for user, or visibility-hidden."""

    code = "PUBLIC_KEY_NOT_FOUND"

    def __init__(self, message: str = "Public key not found.") -> None:
        super().__init__(message)


class KeyOwnershipError(NotFoundError):
    """Key not owned by caller (render as 404 to avoid leaking existence)."""

    code = "NOT_FOUND"

    def __init__(self, message: str = "Key not found.") -> None:
        super().__init__(message)


class ConversationNotFound(NotFoundError):
    """Conversation not found or caller is not a participant."""

    code = "CONVERSATION_NOT_FOUND"

    def __init__(self, message: str = "Conversation not found.") -> None:
        super().__init__(message)


class ConversationIneligible(NotFoundError):
    """Pair is not eligible to message — rendered 404 to avoid user enumeration."""

    code = "CONVERSATION_NOT_FOUND"

    def __init__(self, message: str = "Conversation not found.") -> None:
        super().__init__(message)


class MessageRetentionInvalid(ValidationError):
    """Invalid message_retention_days (must be >= 7)."""

    code = "MESSAGE_RETENTION_INVALID"

    def __init__(self, message: str = "message_retention_days must be >= 7.") -> None:
        super().__init__(message)
