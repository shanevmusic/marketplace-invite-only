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
  static const customerOrders = '/home/customer/orders';
  static const customerMessages = '/home/customer/messages';
  static const customerProfile = '/home/customer/profile';

  static const sellerDashboard = '/home/seller/dashboard';
  static const sellerProducts = '/home/seller/products';
  static const sellerOrders = '/home/seller/orders';
  static const sellerStore = '/home/seller/profile';

  static const driverAvailable = '/home/driver/available';
  static const driverActive = '/home/driver/active';
  static const driverHistory = '/home/driver/history';
  static const driverProfile = '/home/driver/profile';

  static const adminInvites = '/home/admin/invites';
  static const adminUsers = '/home/admin/users';
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
        return adminInvites;
      default:
        return login;
    }
  }
}
