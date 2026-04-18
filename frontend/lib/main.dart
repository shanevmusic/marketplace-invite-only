import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/deep_links/deep_link_handler.dart';
import 'app/router/app_router.dart';
import 'app/theme/app_theme.dart';
import 'features/auth/data/auth_repository.dart';
import 'features/auth/state/auth_controller.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(
    ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(AuthRepository()),
      ],
      child: const MarketplaceApp(),
    ),
  );
}

class MarketplaceApp extends ConsumerStatefulWidget {
  const MarketplaceApp({super.key});

  @override
  ConsumerState<MarketplaceApp> createState() => _MarketplaceAppState();
}

class _MarketplaceAppState extends ConsumerState<MarketplaceApp> {
  DeepLinkHandler? _deepLinks;

  @override
  void initState() {
    super.initState();
    // Kick off the auth controller so /splash resolves.
    ref.read(authControllerProvider);
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final ctx = _navKey.currentContext;
      if (ctx == null) return;
      _deepLinks = ref.read(deepLinkHandlerProvider);
      await _deepLinks!.init(ctx);
    });
  }

  @override
  void dispose() {
    _deepLinks?.dispose();
    super.dispose();
  }

  static final _navKey = GlobalKey<NavigatorState>();

  @override
  Widget build(BuildContext context) {
    final router = ref.watch(goRouterProvider);
    return MaterialApp.router(
      title: 'Marketplace',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: ThemeMode.system,
      routerConfig: router,
    );
  }
}
