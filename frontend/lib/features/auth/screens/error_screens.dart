import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../shared/widgets/app_empty_state.dart';

class OfflineScreen extends StatelessWidget {
  const OfflineScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: AppEmptyState(
          icon: Icons.wifi_off,
          headline: "You're offline",
          subhead: "Sign in once you're back online.",
          ctaLabel: 'Retry',
          onCtaPressed: () => context.go(AppRoutes.splash),
        ),
      ),
    );
  }
}

class InviteInvalidScreen extends StatelessWidget {
  const InviteInvalidScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: AppEmptyState(
          icon: Icons.lock_outline,
          headline: 'Invite unavailable',
          subhead: 'Ask for a new invite or contact who invited you.',
          ctaLabel: 'Close',
          onCtaPressed: () => context.go(AppRoutes.login),
        ),
      ),
    );
  }
}

class UnknownErrorScreen extends StatelessWidget {
  const UnknownErrorScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: AppEmptyState(
          icon: Icons.error_outline,
          headline: 'Something went wrong',
          subhead: 'Try again, or sign out and back in.',
          ctaLabel: 'Go to sign in',
          onCtaPressed: () => context.go(AppRoutes.login),
        ),
      ),
    );
  }
}
