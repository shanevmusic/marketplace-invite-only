import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../data/auth_dtos.dart';
import '../data/auth_repository.dart';

/// Single provider for the app's session state.
///
/// Using a handwritten AsyncNotifier (not @riverpod codegen) in Phase 8 to
/// avoid requiring build_runner in CI. Swappable to codegen in Phase 9+
/// without breaking call sites.
final authRepositoryProvider = Provider<AuthRepository>((ref) {
  throw UnimplementedError(
    'authRepositoryProvider must be overridden in ProviderScope',
  );
});

/// One-shot flag read by the login screen after a session-expired event.
final sessionExpiredFlagProvider = StateProvider<bool>((_) => false);

/// Timeout applied to the boot-time `refresh` call so the splash screen can
/// never hang forever if the backend is slow, unreachable, or misbehaving.
const bootRefreshTimeout = Duration(seconds: 3);

class AuthController extends AsyncNotifier<AuthSession?> {
  @override
  Future<AuthSession?> build() async {
    final repo = ref.read(authRepositoryProvider);
    repo.setSessionExpiredListener(() {
      // Called by the TokenInterceptor on refresh failure.
      ref.read(sessionExpiredFlagProvider.notifier).state = true;
      state = const AsyncValue.data(null);
    });
    final cached = await repo.seedFromStorage();
    if (cached == null) return null;
    try {
      // Attempt a refresh to validate the token on boot (Flow 2).
      // 3s timeout keeps the splash from hanging if backend is slow/unreachable.
      return await repo.refresh().timeout(bootRefreshTimeout);
    } on AuthApiException catch (e) {
      if (e.isTokenExpired || e.isUnauthorized) {
        // Stale tokens — force to unauth.
        await repo.logout();
        ref.read(sessionExpiredFlagProvider.notifier).state = true;
        return null;
      }
      // Network errors: stay optimistically signed-in with cached tokens.
      return cached;
    } catch (_) {
      // Timeout or any other failure during boot refresh: clear in-memory
      // session + secure storage so a corrupt token can't hang the next boot,
      // and let the router fall through to /login.
      try {
        await repo.logout();
      } catch (_) {
        // Ignore logout failures — we're already on the fallback path.
      }
      return null;
    }
  }

  Future<void> login({required String email, required String password}) async {
    state = const AsyncValue.loading();
    final repo = ref.read(authRepositoryProvider);
    state = await AsyncValue.guard(
      () => repo.login(LoginRequest(email: email, password: password)),
    );
  }

  Future<void> signup(SignupRequest body) async {
    state = const AsyncValue.loading();
    final repo = ref.read(authRepositoryProvider);
    state = await AsyncValue.guard(() => repo.signup(body));
  }

  Future<void> logout() async {
    final repo = ref.read(authRepositoryProvider);
    await repo.logout();
    state = const AsyncValue.data(null);
  }
}

final authControllerProvider =
    AsyncNotifierProvider<AuthController, AuthSession?>(AuthController.new);
