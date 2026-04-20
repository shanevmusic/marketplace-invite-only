import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../features/auth/data/auth_dtos.dart';
import '../../features/auth/data/auth_repository.dart' show AuthSession;
import '../../features/auth/screens/error_screens.dart';
import '../../features/auth/screens/invite_landing_screen.dart';
import '../../features/auth/screens/login_screen.dart';
import '../../features/auth/screens/signup_screen.dart';
import '../../features/auth/screens/splash_screen.dart';
import '../../features/auth/state/auth_controller.dart';
import '../../features/checkout/screens/checkout_screen.dart';
import '../../features/delivery_flow/screens/admin_order_tracking_screen.dart';
import '../../features/delivery_flow/screens/customer_delivery_status_screen.dart';
import '../../features/delivery_flow/screens/driver_delivery_map_screen.dart';
import '../../features/delivery_flow/screens/order_chat_screen.dart';
import '../../features/messaging/screens/conversation_detail_screen.dart';
import '../../features/messaging/screens/conversations_list_screen.dart';
import '../../features/orders/screens/customer_order_detail_screen.dart';
import '../../features/orders/screens/seller_order_detail_screen.dart';
import '../../features/products/screens/product_detail_screen.dart';
import '../../features/products/screens/product_form_screen.dart';
import '../../features/products/state/product_controller.dart';
import '../../features/shell/role_shell.dart';
import '../../features/stores/screens/create_store_screen.dart';
import '../../features/stores/screens/edit_store_screen.dart';
import '../../features/settings/screens/account_settings_screen.dart';
import '../../features/settings/screens/change_password_screen.dart';
import '../../features/settings/screens/edit_profile_screen.dart';
import '../../features/admin/screens/admin_account_screen.dart';
import '../../features/settings/screens/notification_prefs_screen.dart';
import '../../features/tracking/customer/screens/customer_tracking_screen.dart';
import '../../features/tracking/driver/screens/driver_tracking_screen.dart';
import '../../features/tracking/seller/screens/seller_tracking_screen.dart';
import 'routes.dart';

/// Returns a [NoTransitionPage] — used for tab switches inside a shell so
/// the content snaps instantly instead of using the platform default
/// fade/scale transition.
Page<T> _noTransitionPage<T>(Widget child) {
  return NoTransitionPage<T>(child: child);
}

/// Listenable that fires when the AuthController's AsyncValue transitions.
/// go_router re-runs the redirect on each notification.
class _AuthRefreshNotifier extends ChangeNotifier {
  _AuthRefreshNotifier(this._ref) {
    _ref.listen<AsyncValue<AuthSession?>>(authControllerProvider, (_, __) {
      notifyListeners();
    });
  }
  final Ref _ref;
}

final _authRefreshProvider =
    Provider<_AuthRefreshNotifier>((ref) => _AuthRefreshNotifier(ref));

final goRouterProvider = Provider<GoRouter>((ref) {
  final refresh = ref.watch(_authRefreshProvider);
  return GoRouter(
    initialLocation: AppRoutes.splash,
    refreshListenable: refresh,
    debugLogDiagnostics: kDebugMode,
    redirect: (ctx, state) => _redirect(ref, state),
    routes: [
      GoRoute(
        path: AppRoutes.splash,
        builder: (_, __) => const SplashScreen(),
      ),
      GoRoute(
        path: AppRoutes.login,
        builder: (_, __) => const LoginScreen(),
      ),
      GoRoute(
        path: AppRoutes.signup,
        builder: (_, s) {
          final extra = s.extra;
          final token = s.uri.queryParameters['invite_token'] ?? '';
          final args = extra is SignupScreenArgs
              ? extra
              : SignupScreenArgs(inviteToken: token);
          return SignupScreen(args: args);
        },
      ),
      GoRoute(
        path: '/invite/:token',
        builder: (_, s) =>
            InviteLandingScreen(token: s.pathParameters['token']!),
      ),
      GoRoute(
        path: AppRoutes.errorOffline,
        builder: (_, __) => const OfflineScreen(),
      ),
      GoRoute(
        path: AppRoutes.errorInviteInvalid,
        builder: (_, __) => const InviteInvalidScreen(),
      ),
      GoRoute(
        path: AppRoutes.errorUnknown,
        builder: (_, __) => const UnknownErrorScreen(),
      ),
      // Checkout — top-level to hide the bottom nav.
      GoRoute(
        path: '/checkout/:sellerId',
        builder: (_, s) =>
            CheckoutScreen(sellerId: s.pathParameters['sellerId']!),
      ),
      // Delivery-flow screens — top-level so bottom nav hides (migration 0010).
      GoRoute(
        path: '/home/customer/orders/:id/delivery',
        builder: (_, s) => CustomerDeliveryStatusScreen(
          orderId: s.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/home/driver/orders/:id/map',
        builder: (_, s) => DriverDeliveryMapScreen(
          orderId: s.pathParameters['id']!,
        ),
      ),
      GoRoute(
        path: '/home/orders/:id/chat',
        builder: (_, s) =>
            OrderChatScreen(orderId: s.pathParameters['id']!),
      ),
      GoRoute(
        path: '/home/admin/orders/:id/tracking',
        builder: (_, s) => AdminOrderTrackingScreen(
          orderId: s.pathParameters['id']!,
        ),
      ),
      // Account settings — top-level full-screen pages (not inside any shell).
      GoRoute(
        path: AppRoutes.accountSettings,
        builder: (_, __) => const AccountSettingsScreen(),
        routes: [
          GoRoute(
            path: 'profile',
            builder: (_, __) => const EditProfileScreen(),
          ),
          GoRoute(
            path: 'password',
            builder: (_, __) => const ChangePasswordScreen(),
          ),
          GoRoute(
            path: 'notifications',
            builder: (_, __) => const NotificationPrefsScreen(),
          ),
        ],
      ),
      GoRoute(
        path: '/home/customer',
        builder: (_, __) => const CustomerShell(),
        routes: _customerSubRoutes,
      ),
      GoRoute(
        path: '/home/seller',
        builder: (_, __) => const SellerShell(),
        routes: _sellerSubRoutes,
      ),
      GoRoute(
        path: '/home/driver',
        builder: (_, __) => const DriverShell(),
        routes: _driverSubRoutes,
      ),
      GoRoute(
        path: '/home/admin',
        builder: (_, __) => const AdminShell(),
        routes: _adminSubRoutes,
      ),
    ],
    errorBuilder: (_, __) => const UnknownErrorScreen(),
  );
});

/// Admin subroutes — each tab path must build AdminShell so deep-link
/// navigation (e.g. /home/admin/users) renders the shell, not a blank
/// SizedBox. The shell reads matchedLocation to pick the active tab.
///
/// Before this fix, admin used the same `:tab → SizedBox.shrink()` pattern
/// as driver (see `_driverSubRoutes`), which caused the AdminShell to never
/// render on deep-link: go_router matched the more specific child builder,
/// and `SizedBox.shrink()` produced a blank (browser-default white) page.
final List<RouteBase> _adminSubRoutes = [
  GoRoute(
    path: 'users',
    pageBuilder: (_, __) => _noTransitionPage(const AdminShell()),
  ),
  GoRoute(
    path: 'drivers',
    pageBuilder: (_, __) => _noTransitionPage(const AdminShell()),
  ),
  GoRoute(
    path: 'orders',
    pageBuilder: (_, __) => _noTransitionPage(const AdminShell()),
  ),
  GoRoute(
    path: 'content',
    pageBuilder: (_, __) => _noTransitionPage(const AdminShell()),
  ),
  GoRoute(
    path: 'analytics',
    pageBuilder: (_, __) => _noTransitionPage(const AdminShell()),
  ),
  // Account is a top-level full-screen page accessed from the AdminShell
  // top-right button (no longer a bottom-nav tab).
  GoRoute(
    path: 'account',
    pageBuilder: (_, __) => _noTransitionPage(const AdminAccountScreen()),
  ),
  // Legacy routes — kept for backward compatibility / deep-links.  Ops
  // and Profile are now folded into the Account page.
  GoRoute(
    path: 'ops',
    pageBuilder: (_, __) => _noTransitionPage(const AdminAccountScreen()),
  ),
  GoRoute(
    path: 'profile',
    pageBuilder: (_, __) => _noTransitionPage(const AdminAccountScreen()),
  ),
];

final List<RouteBase> _customerSubRoutes = [
  GoRoute(
    path: 'discover',
    pageBuilder: (_, __) => _noTransitionPage(const CustomerShell()),
    routes: [
      GoRoute(
        path: 'product/:id',
        parentNavigatorKey: null,
        builder: (_, s) =>
            ProductDetailScreen(productId: s.pathParameters['id']!),
      ),
    ],
  ),
  GoRoute(
    path: 'orders',
    pageBuilder: (_, __) => _noTransitionPage(const CustomerShell()),
    routes: [
      GoRoute(
        path: ':id',
        builder: (_, s) =>
            CustomerOrderDetailScreen(orderId: s.pathParameters['id']!),
        routes: [
          GoRoute(
            path: 'tracking',
            builder: (_, s) =>
                CustomerTrackingScreen(orderId: s.pathParameters['id']!),
          ),
        ],
      ),
    ],
  ),
  GoRoute(
    path: 'cart',
    pageBuilder: (_, __) => _noTransitionPage(const CustomerShell()),
  ),
  GoRoute(
    path: 'messages',
    pageBuilder: (_, __) => _noTransitionPage(const ConversationsListScreen()),
    routes: [
      GoRoute(
        path: ':id',
        builder: (_, s) => ConversationDetailScreen(
          conversationId: s.pathParameters['id']!,
        ),
      ),
    ],
  ),
  GoRoute(
    path: 'profile',
    pageBuilder: (_, __) => _noTransitionPage(const CustomerShell()),
  ),
];

final List<RouteBase> _sellerSubRoutes = [
  GoRoute(
    path: 'dashboard',
    pageBuilder: (_, __) => _noTransitionPage(const SellerShell()),
    routes: [
      GoRoute(
        path: 'store/new',
        builder: (_, __) => const CreateStoreScreen(),
      ),
      GoRoute(
        path: 'store/edit',
        builder: (_, __) => const EditStoreScreen(),
      ),
    ],
  ),
  GoRoute(
    path: 'products',
    pageBuilder: (_, __) => _noTransitionPage(const SellerShell()),
    routes: [
      GoRoute(
        path: 'new',
        builder: (_, __) => const ProductFormScreen(),
      ),
      GoRoute(
        path: ':id/edit',
        builder: (ctx, s) => _ProductEditLoader(
          productId: s.pathParameters['id']!,
        ),
      ),
    ],
  ),
  GoRoute(
    path: 'orders',
    pageBuilder: (_, __) => _noTransitionPage(const SellerShell()),
    routes: [
      GoRoute(
        path: ':id',
        builder: (_, s) =>
            SellerOrderDetailScreen(orderId: s.pathParameters['id']!),
        routes: [
          GoRoute(
            path: 'tracking',
            builder: (_, s) =>
                SellerTrackingScreen(orderId: s.pathParameters['id']!),
          ),
        ],
      ),
    ],
  ),
  GoRoute(
    path: 'messages',
    pageBuilder: (_, __) => _noTransitionPage(const ConversationsListScreen()),
    routes: [
      GoRoute(
        path: ':id',
        builder: (_, s) => ConversationDetailScreen(
          conversationId: s.pathParameters['id']!,
        ),
      ),
    ],
  ),
  GoRoute(
    path: 'profile',
    pageBuilder: (_, __) => _noTransitionPage(const SellerShell()),
  ),
];

final List<RouteBase> _driverSubRoutes = [
  GoRoute(
    path: 'available',
    pageBuilder: (_, __) => _noTransitionPage(const DriverShell()),
  ),
  GoRoute(
    path: 'active',
    pageBuilder: (_, __) => _noTransitionPage(const DriverShell()),
  ),
  GoRoute(
    path: 'history',
    pageBuilder: (_, __) => _noTransitionPage(const DriverShell()),
  ),
  GoRoute(
    path: 'profile',
    pageBuilder: (_, __) => _noTransitionPage(const DriverShell()),
  ),
  GoRoute(
    path: 'orders/:id/tracking',
    builder: (_, s) => DriverTrackingScreen(orderId: s.pathParameters['id']!),
  ),
];

class _ProductEditLoader extends ConsumerWidget {
  const _ProductEditLoader({required this.productId});
  final String productId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(productByIdProvider(productId));
    return async.when(
      loading: () => const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      ),
      error: (_, __) => const Scaffold(
        body: Center(child: Text('Could not load product')),
      ),
      data: (p) => ProductFormScreen(existing: p),
    );
  }
}

@visibleForTesting
String? redirectForTest(ProviderContainer c, String loc) =>
    _redirectAt(c.read(authControllerProvider), loc);

String? _redirect(Ref ref, GoRouterState state) =>
    _redirectAt(ref.read(authControllerProvider), state.matchedLocation);

String? _redirectAt(AsyncValue<AuthSession?> auth, String loc) {

  if (auth.isLoading) {
    return loc == AppRoutes.splash ? null : AppRoutes.splash;
  }

  if (auth.hasError && auth.value == null) {
    if (loc.startsWith('/error/')) return null;
    final err = auth.error;
    if (err is AuthApiException && err.isNetwork) {
      return AppRoutes.errorOffline;
    }
    return AppRoutes.login;
  }

  final session = auth.value;
  // Splash is an initial-state page, not a destination. Once auth has
  // settled (isLoading == false) we must push away from it; leaving splash
  // in `onPublic` strands unauthenticated users on the splash screen
  // forever because the redirect would return null.
  final onPublic = loc == AppRoutes.login ||
      loc == AppRoutes.signup ||
      loc.startsWith('/invite/') ||
      loc.startsWith('/error/');

  if (session == null) {
    return onPublic ? null : AppRoutes.login;
  }

  if (loc == AppRoutes.login ||
      loc == AppRoutes.signup ||
      loc == AppRoutes.splash ||
      loc == '/') {
    return AppRoutes.homeFor(session.user.role);
  }

  final role = session.user.role;
  if (loc.startsWith('/home/customer') && role != 'customer') {
    return AppRoutes.homeFor(role);
  }
  if (loc.startsWith('/home/seller') && role != 'seller') {
    return AppRoutes.homeFor(role);
  }
  if (loc.startsWith('/home/driver') && role != 'driver') {
    return AppRoutes.homeFor(role);
  }
  if (loc.startsWith('/home/admin') && role != 'admin') {
    return AppRoutes.errorUnknown;
  }
  if (loc.startsWith('/checkout/') && role != 'customer') {
    return AppRoutes.homeFor(role);
  }
  return null;
}
