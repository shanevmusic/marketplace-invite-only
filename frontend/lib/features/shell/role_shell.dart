// Role shells for Phase 8. Each shell holds an IndexedStack of tabs where all
// bodies are AppEmptyState placeholders. Discover for unreferred customers
// renders the ADR-0007 "You need a seller invite" empty state from day 1.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';
import '../../shared/widgets/app_app_bar.dart';
import '../../shared/widgets/app_bottom_nav.dart';
import '../../shared/widgets/app_button.dart';
import '../../shared/widgets/app_dialog.dart';
import '../../shared/widgets/app_empty_state.dart';
import '../../shared/widgets/app_list_tile.dart';
import '../../shared/widgets/app_snackbar.dart';
import '../auth/state/auth_controller.dart';

class _TabSpec {
  const _TabSpec({
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.body,
    this.title,
  });
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final Widget body;
  final String? title;
}

String? _currentIndexForRoute(String location, List<String> tabPaths) {
  for (final p in tabPaths) {
    if (location.startsWith(p)) return p;
  }
  return null;
}

class _ShellScaffold extends ConsumerStatefulWidget {
  const _ShellScaffold({
    required this.title,
    required this.tabs,
    this.fab,
  });

  final String title;
  final List<_TabSpec> tabs;
  final Widget? fab;

  @override
  ConsumerState<_ShellScaffold> createState() => _ShellScaffoldState();
}

class _ShellScaffoldState extends ConsumerState<_ShellScaffold> {
  int _index = 0;

  @override
  Widget build(BuildContext context) {
    final tab = widget.tabs[_index];
    return Scaffold(
      appBar: AppTopBar(title: tab.title ?? widget.title),
      body: SafeArea(
        child: IndexedStack(
          index: _index,
          children: [for (final t in widget.tabs) t.body],
        ),
      ),
      floatingActionButton: widget.fab,
      bottomNavigationBar: AppBottomNav(
        currentIndex: _index,
        onTap: (i) => setState(() => _index = i),
        items: [
          for (final t in widget.tabs)
            AppBottomNavItem(
              icon: t.icon,
              activeIcon: t.activeIcon,
              label: t.label,
            ),
        ],
      ),
    );
  }
}

// ---------- Customer ----------

class CustomerShell extends ConsumerWidget {
  const CustomerShell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _ShellScaffold(
      title: 'Discover',
      tabs: [
        _TabSpec(
          icon: Icons.storefront_outlined,
          activeIcon: Icons.storefront,
          label: 'Discover',
          title: 'Discover',
          // ADR-0007 referral-scoped empty state. Never shown as "no products".
          body: const AppEmptyState(
            icon: Icons.lock_outline,
            headline: 'You need a seller invite',
            subhead:
                'This marketplace is invite-only. Ask a seller for their '
                'referral link, then open it to unlock their store.',
            ctaLabel: 'How invites work',
          ),
        ),
        _TabSpec(
          icon: Icons.receipt_long_outlined,
          activeIcon: Icons.receipt_long,
          label: 'Orders',
          title: 'Orders',
          body: const AppEmptyState(
            icon: Icons.receipt_long_outlined,
            headline: 'No orders yet',
            subhead: "When you place an order, it'll appear here.",
          ),
        ),
        _TabSpec(
          icon: Icons.chat_bubble_outline,
          activeIcon: Icons.chat_bubble,
          label: 'Messages',
          title: 'Messages',
          body: const AppEmptyState(
            icon: Icons.chat_bubble_outline,
            headline: 'No messages yet',
            subhead: 'Conversations with your seller appear here.',
          ),
        ),
        _TabSpec(
          icon: Icons.person_outline,
          activeIcon: Icons.person,
          label: 'Profile',
          title: 'Profile',
          body: const ProfileTab(),
        ),
      ],
    );
  }
}

// ---------- Seller ----------

class SellerShell extends ConsumerWidget {
  const SellerShell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _ShellScaffold(
      title: 'Dashboard',
      tabs: [
        _TabSpec(
          icon: Icons.dashboard_outlined,
          activeIcon: Icons.dashboard,
          label: 'Dashboard',
          title: 'Dashboard',
          body: AppEmptyState(
            icon: Icons.storefront_outlined,
            headline: 'Create your store',
            subhead: 'Give it a name and city so customers can find you.',
            ctaLabel: 'Create store',
            onCtaPressed: () {},
          ),
        ),
        _TabSpec(
          icon: Icons.inventory_2_outlined,
          activeIcon: Icons.inventory_2,
          label: 'Products',
          title: 'Products',
          body: const AppEmptyState(
            icon: Icons.inventory_2_outlined,
            headline: 'No products yet',
            subhead: 'Add your first product to start selling.',
          ),
        ),
        _TabSpec(
          icon: Icons.receipt_long_outlined,
          activeIcon: Icons.receipt_long,
          label: 'Orders',
          title: 'Orders',
          body: const AppEmptyState(
            icon: Icons.receipt_long_outlined,
            headline: 'No orders yet',
            subhead: 'Orders from your customers will appear here.',
          ),
        ),
        _TabSpec(
          icon: Icons.store_outlined,
          activeIcon: Icons.store,
          label: 'Store',
          title: 'Store',
          body: const ProfileTab(),
        ),
      ],
    );
  }
}

// ---------- Driver ----------

class DriverShell extends ConsumerWidget {
  const DriverShell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _ShellScaffold(
      title: 'Available deliveries',
      tabs: [
        _TabSpec(
          icon: Icons.list_alt_outlined,
          activeIcon: Icons.list_alt,
          label: 'Available',
          title: 'Available deliveries',
          body: const AppEmptyState(
            icon: Icons.list_alt_outlined,
            headline: 'No deliveries assigned',
            subhead:
                "When admin assigns you a delivery, it'll appear here.",
          ),
        ),
        _TabSpec(
          icon: Icons.local_shipping_outlined,
          activeIcon: Icons.local_shipping,
          label: 'Active',
          title: 'No active delivery',
          body: const AppEmptyState(
            icon: Icons.local_shipping_outlined,
            headline: 'Nothing active right now',
            subhead: 'Accept a delivery from the Available tab to start.',
          ),
        ),
        _TabSpec(
          icon: Icons.history,
          activeIcon: Icons.history,
          label: 'History',
          title: 'Completed',
          body: const AppEmptyState(
            icon: Icons.history,
            headline: 'No completed deliveries yet',
          ),
        ),
        _TabSpec(
          icon: Icons.person_outline,
          activeIcon: Icons.person,
          label: 'Profile',
          title: 'Profile',
          body: const ProfileTab(),
        ),
      ],
    );
  }
}

// ---------- Admin ----------

class AdminShell extends ConsumerWidget {
  const AdminShell({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return _ShellScaffold(
      title: 'Invites',
      tabs: [
        _TabSpec(
          icon: Icons.mail_outline,
          activeIcon: Icons.mail,
          label: 'Invites',
          title: 'Invites',
          body: const AppEmptyState(
            icon: Icons.mail_outline,
            headline: 'Issue your first invite',
            subhead:
                'Seed the network by inviting a seller or another admin.',
          ),
        ),
        _TabSpec(
          icon: Icons.people_outline,
          activeIcon: Icons.people,
          label: 'Users',
          title: 'Users',
          body: const AppEmptyState(
            icon: Icons.people_outline,
            headline: 'Just you so far',
            subhead:
                'Invite sellers and drivers to populate the network.',
          ),
        ),
        _TabSpec(
          icon: Icons.settings_outlined,
          activeIcon: Icons.settings,
          label: 'Settings',
          title: 'Platform settings',
          body: const AppEmptyState(
            icon: Icons.settings_outlined,
            headline: 'Platform settings',
            subhead: 'Retention, grace hours, and other defaults.',
          ),
        ),
        _TabSpec(
          icon: Icons.event_note_outlined,
          activeIcon: Icons.event_note,
          label: 'Logs',
          title: 'Activity',
          body: const AppEmptyState(
            icon: Icons.event_note_outlined,
            headline: 'No activity yet',
          ),
        ),
      ],
    );
  }
}

// ---------- Shared profile tab ----------

class ProfileTab extends ConsumerWidget {
  const ProfileTab({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final session = ref.watch(authControllerProvider).valueOrNull;
    if (session == null) {
      return const AppEmptyState(
        icon: Icons.person_outline,
        headline: 'Not signed in',
      );
    }
    return ListView(
      children: [
        Padding(
          padding: const EdgeInsets.all(AppSpacing.s4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(session.user.displayName,
                  style: context.textStyles.headlineSmall),
              const SizedBox(height: AppSpacing.s1),
              Text(session.user.email,
                  style: context.textStyles.bodyMedium?.copyWith(
                    color: context.colors.onSurfaceVariant,
                  )),
            ],
          ),
        ),
        AppListTile(
          leading: const Icon(Icons.badge_outlined),
          title: 'Role',
          subtitle: session.user.role,
        ),
        Padding(
          padding: const EdgeInsets.all(AppSpacing.s4),
          child: AppButton(
            label: 'Sign out',
            variant: AppButtonVariant.destructive,
            expand: true,
            onPressed: () => _confirmLogout(context, ref),
          ),
        ),
      ],
    );
  }

  Future<void> _confirmLogout(BuildContext context, WidgetRef ref) async {
    await AppDialog.show(
      context,
      title: 'Sign out of this account?',
      body: const SizedBox.shrink(),
      primaryAction: AppDialogAction(
        label: 'Sign out',
        destructive: true,
        onPressed: () async {
          Navigator.of(context).pop();
          await ref.read(authControllerProvider.notifier).logout();
          if (context.mounted) {
            context.showAppSnackbar(message: 'Signed out.');
          }
        },
      ),
      secondaryAction: AppDialogAction(
        label: 'Cancel',
        onPressed: () => Navigator.of(context).pop(),
      ),
    );
  }
}
