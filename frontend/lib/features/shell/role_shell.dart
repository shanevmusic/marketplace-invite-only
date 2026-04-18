// Role shells for Phase 9 — each shell routes the selected tab to a real
// screen. The shell uses IndexedStack for instant tab switching; navigation
// to detail screens (product, order, checkout) happens via GoRouter outside
// the shell (frontend-spec/phase-9-navigation-additions.md §4).
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../app/router/routes.dart';
import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';
import '../../shared/widgets/app_app_bar.dart';
import '../../shared/widgets/app_bottom_nav.dart';
import '../../shared/widgets/app_button.dart';
import '../../shared/widgets/app_dialog.dart';
import '../../shared/widgets/app_empty_state.dart';
import '../../shared/widgets/app_list_tile.dart';
import '../../shared/widgets/app_snackbar.dart';
import '../../shared/widgets/tab_badge.dart';
import '../auth/state/auth_controller.dart';
import '../cart/cart_store.dart';
import '../cart/screens/cart_screen.dart';
import '../discover/screens/discover_screen.dart';
import '../orders/screens/customer_orders_screen.dart';
import '../orders/screens/seller_orders_screen.dart';
import '../products/screens/seller_products_screen.dart';
import '../sellers/screens/seller_dashboard_screen.dart';

class _TabSpec {
  const _TabSpec({
    required this.icon,
    required this.activeIcon,
    required this.label,
    required this.path,
    required this.body,
    this.title,
  });
  final IconData icon;
  final IconData activeIcon;
  final String label;
  final String path;
  final Widget body;
  final String? title;
}

int _indexForLocation(String loc, List<_TabSpec> tabs) {
  for (int i = 0; i < tabs.length; i++) {
    if (loc.startsWith(tabs[i].path)) return i;
  }
  return 0;
}

class _ShellScaffold extends ConsumerWidget {
  const _ShellScaffold({required this.title, required this.tabs});
  final String title;
  final List<_TabSpec> tabs;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final loc = GoRouterState.of(context).matchedLocation;
    final idx = _indexForLocation(loc, tabs);
    final tab = tabs[idx];
    return Scaffold(
      appBar: AppTopBar(title: tab.title ?? title),
      body: SafeArea(
        child: IndexedStack(
          index: idx,
          children: [for (final t in tabs) t.body],
        ),
      ),
      bottomNavigationBar: AppBottomNav(
        currentIndex: idx,
        onTap: (i) => context.go(tabs[i].path),
        items: [
          for (final t in tabs)
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
    final cartCount = ref.watch(cartControllerProvider).valueOrNull?.totalItems ?? 0;
    return _ShellScaffold(
      title: 'Discover',
      tabs: [
        const _TabSpec(
          icon: Icons.storefront_outlined,
          activeIcon: Icons.storefront,
          label: 'Discover',
          path: AppRoutes.customerDiscover,
          title: 'Discover',
          body: DiscoverScreen(),
        ),
        _TabSpec(
          icon: Icons.shopping_cart_outlined,
          activeIcon: Icons.shopping_cart,
          label: 'Cart',
          path: AppRoutes.customerCart,
          title: 'Cart',
          body: _CartBadgeWrap(count: cartCount, child: const CartScreen()),
        ),
        const _TabSpec(
          icon: Icons.receipt_long_outlined,
          activeIcon: Icons.receipt_long,
          label: 'Orders',
          path: AppRoutes.customerOrders,
          title: 'Orders',
          body: CustomerOrdersScreen(),
        ),
        const _TabSpec(
          icon: Icons.person_outline,
          activeIcon: Icons.person,
          label: 'Profile',
          path: AppRoutes.customerProfile,
          title: 'Profile',
          body: ProfileTab(),
        ),
      ],
    );
  }
}

class _CartBadgeWrap extends StatelessWidget {
  const _CartBadgeWrap({required this.count, required this.child});
  final int count;
  final Widget child;
  @override
  Widget build(BuildContext context) {
    if (count <= 0) return child;
    return Stack(
      children: [
        child,
        Positioned(
          right: 12,
          top: 12,
          child: TabBadge(child: const SizedBox.shrink(), count: count),
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
      tabs: const [
        _TabSpec(
          icon: Icons.dashboard_outlined,
          activeIcon: Icons.dashboard,
          label: 'Dashboard',
          path: AppRoutes.sellerDashboard,
          title: 'Dashboard',
          body: SellerDashboardScreen(),
        ),
        _TabSpec(
          icon: Icons.inventory_2_outlined,
          activeIcon: Icons.inventory_2,
          label: 'Products',
          path: AppRoutes.sellerProducts,
          title: 'Products',
          body: SellerProductsScreen(),
        ),
        _TabSpec(
          icon: Icons.receipt_long_outlined,
          activeIcon: Icons.receipt_long,
          label: 'Orders',
          path: AppRoutes.sellerOrders,
          title: 'Orders',
          body: SellerOrdersScreen(),
        ),
        _TabSpec(
          icon: Icons.store_outlined,
          activeIcon: Icons.store,
          label: 'Store',
          path: AppRoutes.sellerStore,
          title: 'Store',
          body: ProfileTab(),
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
      tabs: const [
        _TabSpec(
          icon: Icons.list_alt_outlined,
          activeIcon: Icons.list_alt,
          label: 'Available',
          path: AppRoutes.driverAvailable,
          title: 'Available deliveries',
          body: AppEmptyState(
            icon: Icons.list_alt_outlined,
            headline: 'No deliveries assigned',
            subhead: "When admin assigns you a delivery, it'll appear here.",
          ),
        ),
        _TabSpec(
          icon: Icons.local_shipping_outlined,
          activeIcon: Icons.local_shipping,
          label: 'Active',
          path: AppRoutes.driverActive,
          title: 'No active delivery',
          body: AppEmptyState(
            icon: Icons.local_shipping_outlined,
            headline: 'Nothing active right now',
            subhead: 'Accept a delivery from the Available tab to start.',
          ),
        ),
        _TabSpec(
          icon: Icons.history,
          activeIcon: Icons.history,
          label: 'History',
          path: AppRoutes.driverHistory,
          title: 'Completed',
          body: AppEmptyState(
            icon: Icons.history,
            headline: 'No completed deliveries yet',
          ),
        ),
        _TabSpec(
          icon: Icons.person_outline,
          activeIcon: Icons.person,
          label: 'Profile',
          path: AppRoutes.driverProfile,
          title: 'Profile',
          body: ProfileTab(),
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
      tabs: const [
        _TabSpec(
          icon: Icons.mail_outline,
          activeIcon: Icons.mail,
          label: 'Invites',
          path: AppRoutes.adminInvites,
          title: 'Invites',
          body: AppEmptyState(
            icon: Icons.mail_outline,
            headline: 'Issue your first invite',
            subhead: 'Seed the network by inviting a seller or another admin.',
          ),
        ),
        _TabSpec(
          icon: Icons.people_outline,
          activeIcon: Icons.people,
          label: 'Users',
          path: AppRoutes.adminUsers,
          title: 'Users',
          body: AppEmptyState(
            icon: Icons.people_outline,
            headline: 'Just you so far',
            subhead: 'Invite sellers and drivers to populate the network.',
          ),
        ),
        _TabSpec(
          icon: Icons.settings_outlined,
          activeIcon: Icons.settings,
          label: 'Settings',
          path: AppRoutes.adminSettings,
          title: 'Platform settings',
          body: AppEmptyState(
            icon: Icons.settings_outlined,
            headline: 'Platform settings',
            subhead: 'Retention, grace hours, and other defaults.',
          ),
        ),
        _TabSpec(
          icon: Icons.event_note_outlined,
          activeIcon: Icons.event_note,
          label: 'Logs',
          path: AppRoutes.adminLogs,
          title: 'Activity',
          body: AppEmptyState(
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
