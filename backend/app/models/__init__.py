"""SQLAlchemy ORM models — one module per aggregate.

Importing this package registers all model classes against ``Base.metadata``,
which is required for Alembic auto-generation to discover every table.
"""

# Import order matters: models with FKs must be imported after the tables
# they reference, but SQLAlchemy resolves FK strings lazily so the order
# here is mainly for readability.

from app.models.user import User  # noqa: F401
from app.models.refresh_token import RefreshToken  # noqa: F401
from app.models.invite_link import InviteLink  # noqa: F401
from app.models.referral import Referral  # noqa: F401
from app.models.seller import Seller  # noqa: F401
from app.models.store import Store  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.product_image import ProductImage  # noqa: F401
from app.models.cart_item import CartItem  # noqa: F401
from app.models.order import Order  # noqa: F401
from app.models.order_item import OrderItem  # noqa: F401
from app.models.delivery import Delivery  # noqa: F401
from app.models.driver_assignment import DriverAssignment  # noqa: F401
from app.models.conversation import Conversation  # noqa: F401
from app.models.message import Message  # noqa: F401
from app.models.user_public_key import UserPublicKey  # noqa: F401
from app.models.review import Review  # noqa: F401
from app.models.platform_settings import PlatformSettings  # noqa: F401
from app.models.order_analytics_snapshot import OrderAnalyticsSnapshot  # noqa: F401
from app.models.user_device import UserDevice  # noqa: F401
from app.models.user_notification_prefs import UserNotificationPrefs  # noqa: F401
from app.models.delivery_flow import (  # noqa: F401
    DeliveryCode,
    DeliveryCodeAttempt,
    OrderMessage,
    OrderTrackingPoint,
)

__all__ = [
    "User",
    "RefreshToken",
    "InviteLink",
    "Referral",
    "Seller",
    "Store",
    "Product",
    "ProductImage",
    "CartItem",
    "Order",
    "OrderItem",
    "Delivery",
    "DriverAssignment",
    "Conversation",
    "Message",
    "UserPublicKey",
    "Review",
    "PlatformSettings",
    "OrderAnalyticsSnapshot",
    "UserDevice",
    "UserNotificationPrefs",
    "DeliveryCode",
    "DeliveryCodeAttempt",
    "OrderMessage",
    "OrderTrackingPoint",
]
