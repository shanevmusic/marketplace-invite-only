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
import '../../features/shell/role_shell.dart';
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
      GoRoute(
        path: '/home/customer',
        builder: (_, __) => const CustomerShell(),
        routes: _roleSubRoutes,
      ),
      GoRoute(
        path: '/home/seller',
        builder: (_, __) => const SellerShell(),
        routes: _roleSubRoutes,
      ),
      GoRoute(
        path: '/home/driver',
        builder: (_, __) => const DriverShell(),
        routes: _roleSubRoutes,
      ),
      GoRoute(
        path: '/home/admin',
        builder: (_, __) => const AdminShell(),
        routes: _roleSubRoutes,
      ),
    ],
    errorBuilder: (_, __) => const UnknownErrorScreen(),
  );
});

/// Catch-all child matcher so deep-link tab paths land on the shell.
final List<RouteBase> _roleSubRoutes = [
  GoRoute(
    path: ':tab',
    builder: (_, __) => const SizedBox.shrink(),
  ),
];

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

  // Authed user wandered into an unauth-only route.
  if (loc == AppRoutes.login ||
      loc == AppRoutes.signup ||
      loc == AppRoutes.splash ||
      loc == '/') {
    return AppRoutes.homeFor(session.user.role);
  }

  // Role-guarded shells.
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
    return AppRoutes.homeFor(role);
  }
  return null;
}
