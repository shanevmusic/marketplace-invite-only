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
import '../../features/messaging/screens/conversation_detail_screen.dart';
import '../../features/messaging/screens/conversations_list_screen.dart';
import '../../features/orders/screens/customer_order_detail_screen.dart';
import '../../features/orders/screens/seller_order_detail_screen.dart';
import '../../features/products/screens/product_detail_screen.dart';
import '../../features/products/screens/product_form_screen.dart';
import '../../features/products/state/product_controller.dart';
import '../../features/shell/role_shell.dart';
import '../../features/stores/screens/create_store_screen.dart';
import '../../features/tracking/customer/screens/customer_tracking_screen.dart';
import '../../features/tracking/driver/screens/driver_tracking_screen.dart';
import '../../features/tracking/seller/screens/seller_tracking_screen.dart';
import 'routes.dart';

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
        routes: _basicSubRoutes,
      ),
    ],
    errorBuilder: (_, __) => const UnknownErrorScreen(),
  );
});

/// Catch-all child matcher so deep-link tab paths land on the shell.
final List<RouteBase> _basicSubRoutes = [
  GoRoute(
    path: ':tab',
    builder: (_, __) => const SizedBox.shrink(),
  ),
];

final List<RouteBase> _customerSubRoutes = [
  GoRoute(
    path: 'discover',
    builder: (_, __) => const CustomerShell(),
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
    builder: (_, __) => const CustomerShell(),
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
    builder: (_, __) => const CustomerShell(),
  ),
  GoRoute(
    path: 'messages',
    builder: (_, __) => const ConversationsListScreen(),
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
    builder: (_, __) => const CustomerShell(),
  ),
];

final List<RouteBase> _sellerSubRoutes = [
  GoRoute(
    path: 'dashboard',
    builder: (_, __) => const SellerShell(),
    routes: [
      GoRoute(
        path: 'store/new',
        builder: (_, __) => const CreateStoreScreen(),
      ),
    ],
  ),
  GoRoute(
    path: 'products',
    builder: (_, __) => const SellerShell(),
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
    builder: (_, __) => const SellerShell(),
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
    builder: (_, __) => const ConversationsListScreen(),
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
    builder: (_, __) => const SellerShell(),
  ),
];

final List<RouteBase> _driverSubRoutes = [
  GoRoute(
    path: ':tab',
    builder: (_, __) => const SizedBox.shrink(),
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

String? _redirect(Ref ref, GoRouterState state) {
  final auth = ref.read(authControllerProvider);
  final loc = state.matchedLocation;

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
  final onPublic = loc == AppRoutes.login ||
      loc == AppRoutes.signup ||
      loc.startsWith('/invite/') ||
      loc == AppRoutes.splash ||
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
