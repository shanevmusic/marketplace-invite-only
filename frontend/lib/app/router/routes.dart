/// Canonical path constants. No widget or test uses a raw path outside this
/// file (frontend-spec/04-navigation-map.md §7).
abstract class AppRoutes {
  static const splash = '/splash';
  static const login = '/login';
  static const signup = '/signup';
  static const roleChoice = '/signup/role-choice';
  static String invite(String token) => '/invite/$token';
  static const errorOffline = '/error/offline';
  static const errorInviteInvalid = '/error/invite-invalid';
  static const errorUnknown = '/error/unknown';

  static const customerHome = '/home/customer';
  static const sellerHome = '/home/seller';
  static const driverHome = '/home/driver';
  static const adminHome = '/home/admin';

  static const customerDiscover = '/home/customer/discover';
  static const customerCart = '/home/customer/cart';
  static const customerOrders = '/home/customer/orders';
  static const customerMessages = '/home/customer/messages';
  static const customerProfile = '/home/customer/profile';

  static String customerProduct(String id) => '$customerDiscover/product/$id';
  static String customerSeller(String id) => '$customerDiscover/seller/$id';
  static String customerOrderDetail(String id) => '$customerOrders/$id';

  /// Checkout is top-level so the bottom nav hides (frontend-spec/phase-9-navigation-additions.md §4).
  static String checkout(String sellerId) => '/checkout/$sellerId';

  static const sellerDashboard = '/home/seller/dashboard';
  static const sellerProducts = '/home/seller/products';
  static const sellerOrders = '/home/seller/orders';
  static const sellerStore = '/home/seller/profile';
  static const sellerStoreNew = '/home/seller/dashboard/store/new';
  static String sellerProductNew() => '$sellerProducts/new';
  static String sellerProductEdit(String id) => '$sellerProducts/$id/edit';
  static String sellerOrderDetail(String id) => '$sellerOrders/$id';

  static const driverAvailable = '/home/driver/available';
  static const driverActive = '/home/driver/active';
  static const driverHistory = '/home/driver/history';
  static const driverProfile = '/home/driver/profile';

  static const adminInvites = '/home/admin/invites';
  static const adminUsers = '/home/admin/users';
  static const adminContent = '/home/admin/content';
  static const adminAnalytics = '/home/admin/analytics';
  static const adminOps = '/home/admin/ops';
  static const adminSettings = '/home/admin/settings';
  static const adminLogs = '/home/admin/logs';

  /// Resolves the default landing path for a given role.
  static String homeFor(String role) {
    switch (role) {
      case 'customer':
        return customerDiscover;
      case 'seller':
        return sellerDashboard;
      case 'driver':
        return driverAvailable;
      case 'admin':
        return adminUsers;
      default:
        return login;
    }
  }
}
