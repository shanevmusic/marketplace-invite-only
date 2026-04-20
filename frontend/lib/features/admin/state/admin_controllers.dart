import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import '../data/admin_api.dart';
import '../data/admin_dtos.dart';

final adminApiProvider = Provider<AdminApi>((ref) {
  return AdminApi(ref.watch(apiClientProvider));
});

// ---------------------------------------------------------------------------
// Users
// ---------------------------------------------------------------------------

class AdminUsersFilter {
  const AdminUsersFilter({this.q, this.role, this.status});
  final String? q;
  final String? role;
  final String? status;

  AdminUsersFilter copyWith({
    String? q,
    String? role,
    String? status,
    bool clearQ = false,
    bool clearRole = false,
    bool clearStatus = false,
  }) {
    return AdminUsersFilter(
      q: clearQ ? null : (q ?? this.q),
      role: clearRole ? null : (role ?? this.role),
      status: clearStatus ? null : (status ?? this.status),
    );
  }
}

class AdminUsersState {
  const AdminUsersState({
    required this.filter,
    required this.users,
    required this.nextCursor,
    required this.isLoadingMore,
  });
  final AdminUsersFilter filter;
  final List<AdminUserSummary> users;
  final String? nextCursor;
  final bool isLoadingMore;

  bool get hasMore => nextCursor != null;

  AdminUsersState copyWith({
    AdminUsersFilter? filter,
    List<AdminUserSummary>? users,
    String? nextCursor,
    bool? isLoadingMore,
    bool clearCursor = false,
  }) {
    return AdminUsersState(
      filter: filter ?? this.filter,
      users: users ?? this.users,
      nextCursor: clearCursor ? null : (nextCursor ?? this.nextCursor),
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    );
  }
}

class AdminUsersController extends AsyncNotifier<AdminUsersState> {
  @override
  Future<AdminUsersState> build() async {
    final api = ref.read(adminApiProvider);
    final page = await api.listUsers();
    return AdminUsersState(
      filter: const AdminUsersFilter(),
      users: page.data,
      nextCursor: page.nextCursor,
      isLoadingMore: false,
    );
  }

  Future<void> applyFilter(AdminUsersFilter filter) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final page = await ref.read(adminApiProvider).listUsers(
            q: filter.q,
            role: filter.role,
            status: filter.status,
          );
      return AdminUsersState(
        filter: filter,
        users: page.data,
        nextCursor: page.nextCursor,
        isLoadingMore: false,
      );
    });
  }

  Future<void> loadMore() async {
    final current = state.valueOrNull;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final page = await ref.read(adminApiProvider).listUsers(
            q: current.filter.q,
            role: current.filter.role,
            status: current.filter.status,
            cursor: current.nextCursor,
          );
      state = AsyncValue.data(
        current.copyWith(
          users: [...current.users, ...page.data],
          nextCursor: page.nextCursor,
          clearCursor: page.nextCursor == null,
          isLoadingMore: false,
        ),
      );
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }

  Future<void> suspend(String userId, String reason) async {
    await ref.read(adminApiProvider).suspendUser(userId, reason);
    await applyFilter(state.valueOrNull?.filter ?? const AdminUsersFilter());
  }

  Future<void> unsuspend(String userId) async {
    await ref.read(adminApiProvider).unsuspendUser(userId);
    await applyFilter(state.valueOrNull?.filter ?? const AdminUsersFilter());
  }
}

final adminUsersControllerProvider =
    AsyncNotifierProvider<AdminUsersController, AdminUsersState>(
        AdminUsersController.new);

final adminUserDetailProvider =
    FutureProvider.family<AdminUserDetail, String>((ref, id) async {
  return ref.read(adminApiProvider).getUser(id);
});

// ---------------------------------------------------------------------------
// Products
// ---------------------------------------------------------------------------

class AdminProductsFilter {
  const AdminProductsFilter({this.q, this.status});
  final String? q;
  final String? status;
}

class AdminProductsState {
  const AdminProductsState({
    required this.filter,
    required this.products,
    required this.nextCursor,
  });
  final AdminProductsFilter filter;
  final List<AdminProductSummary> products;
  final String? nextCursor;
}

class AdminProductsController extends AsyncNotifier<AdminProductsState> {
  @override
  Future<AdminProductsState> build() async {
    final page = await ref.read(adminApiProvider).listProducts();
    return AdminProductsState(
      filter: const AdminProductsFilter(),
      products: page.data,
      nextCursor: page.nextCursor,
    );
  }

  Future<void> applyFilter(AdminProductsFilter f) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final page = await ref.read(adminApiProvider).listProducts(
            q: f.q,
            status: f.status,
          );
      return AdminProductsState(
        filter: f,
        products: page.data,
        nextCursor: page.nextCursor,
      );
    });
  }

  Future<void> disable(String id, String reason) async {
    await ref.read(adminApiProvider).disableProduct(id, reason);
    await applyFilter(
        state.valueOrNull?.filter ?? const AdminProductsFilter());
  }

  Future<void> restore(String id) async {
    await ref.read(adminApiProvider).restoreProduct(id);
    await applyFilter(
        state.valueOrNull?.filter ?? const AdminProductsFilter());
  }
}

final adminProductsControllerProvider =
    AsyncNotifierProvider<AdminProductsController, AdminProductsState>(
        AdminProductsController.new);

// ---------------------------------------------------------------------------
// Drivers (specialised view of /admin/users?role=driver)
// ---------------------------------------------------------------------------

class AdminDriversState {
  const AdminDriversState({
    required this.drivers,
    required this.nextCursor,
    required this.isLoadingMore,
  });
  final List<AdminUserSummary> drivers;
  final String? nextCursor;
  final bool isLoadingMore;

  bool get hasMore => nextCursor != null;

  AdminDriversState copyWith({
    List<AdminUserSummary>? drivers,
    String? nextCursor,
    bool? isLoadingMore,
    bool clearCursor = false,
  }) {
    return AdminDriversState(
      drivers: drivers ?? this.drivers,
      nextCursor: clearCursor ? null : (nextCursor ?? this.nextCursor),
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    );
  }
}

class AdminDriversController extends AsyncNotifier<AdminDriversState> {
  @override
  Future<AdminDriversState> build() async {
    final page =
        await ref.read(adminApiProvider).listUsers(role: 'driver');
    return AdminDriversState(
      drivers: page.data,
      nextCursor: page.nextCursor,
      isLoadingMore: false,
    );
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final page =
          await ref.read(adminApiProvider).listUsers(role: 'driver');
      return AdminDriversState(
        drivers: page.data,
        nextCursor: page.nextCursor,
        isLoadingMore: false,
      );
    });
  }

  Future<void> loadMore() async {
    final current = state.valueOrNull;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final page = await ref.read(adminApiProvider).listUsers(
            role: 'driver',
            cursor: current.nextCursor,
          );
      state = AsyncValue.data(
        current.copyWith(
          drivers: [...current.drivers, ...page.data],
          nextCursor: page.nextCursor,
          clearCursor: page.nextCursor == null,
          isLoadingMore: false,
        ),
      );
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final adminDriversControllerProvider =
    AsyncNotifierProvider<AdminDriversController, AdminDriversState>(
        AdminDriversController.new);

// ---------------------------------------------------------------------------
// Orders (admin oversight)
// ---------------------------------------------------------------------------

class AdminOrdersFilter {
  const AdminOrdersFilter({this.status});
  final String? status;
}

class AdminOrdersState {
  const AdminOrdersState({
    required this.filter,
    required this.orders,
    required this.nextCursor,
    required this.isLoadingMore,
  });
  final AdminOrdersFilter filter;
  final List<AdminOrderSummary> orders;
  final String? nextCursor;
  final bool isLoadingMore;

  bool get hasMore => nextCursor != null;

  AdminOrdersState copyWith({
    AdminOrdersFilter? filter,
    List<AdminOrderSummary>? orders,
    String? nextCursor,
    bool? isLoadingMore,
    bool clearCursor = false,
  }) {
    return AdminOrdersState(
      filter: filter ?? this.filter,
      orders: orders ?? this.orders,
      nextCursor: clearCursor ? null : (nextCursor ?? this.nextCursor),
      isLoadingMore: isLoadingMore ?? this.isLoadingMore,
    );
  }
}

class AdminOrdersController extends AsyncNotifier<AdminOrdersState> {
  @override
  Future<AdminOrdersState> build() async {
    final page = await ref.read(adminApiProvider).listOrders();
    return AdminOrdersState(
      filter: const AdminOrdersFilter(),
      orders: page.data,
      nextCursor: page.nextCursor,
      isLoadingMore: false,
    );
  }

  Future<void> applyFilter(AdminOrdersFilter f) async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final page =
          await ref.read(adminApiProvider).listOrders(status: f.status);
      return AdminOrdersState(
        filter: f,
        orders: page.data,
        nextCursor: page.nextCursor,
        isLoadingMore: false,
      );
    });
  }

  Future<void> loadMore() async {
    final current = state.valueOrNull;
    if (current == null || !current.hasMore || current.isLoadingMore) return;
    state = AsyncValue.data(current.copyWith(isLoadingMore: true));
    try {
      final page = await ref.read(adminApiProvider).listOrders(
            status: current.filter.status,
            cursor: current.nextCursor,
          );
      state = AsyncValue.data(
        current.copyWith(
          orders: [...current.orders, ...page.data],
          nextCursor: page.nextCursor,
          clearCursor: page.nextCursor == null,
          isLoadingMore: false,
        ),
      );
    } catch (e, st) {
      state = AsyncValue.error(e, st);
    }
  }
}

final adminOrdersControllerProvider =
    AsyncNotifierProvider<AdminOrdersController, AdminOrdersState>(
        AdminOrdersController.new);

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

class AdminAnalyticsState {
  const AdminAnalyticsState({required this.overview, required this.topSellers});
  final AdminAnalyticsOverview overview;
  final List<TopSeller> topSellers;
}

class AdminAnalyticsController extends AsyncNotifier<AdminAnalyticsState> {
  @override
  Future<AdminAnalyticsState> build() async {
    final api = ref.read(adminApiProvider);
    final results = await Future.wait([api.overview(), api.topSellers()]);
    return AdminAnalyticsState(
      overview: results[0] as AdminAnalyticsOverview,
      topSellers: results[1] as List<TopSeller>,
    );
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final api = ref.read(adminApiProvider);
      final results = await Future.wait([api.overview(), api.topSellers()]);
      return AdminAnalyticsState(
        overview: results[0] as AdminAnalyticsOverview,
        topSellers: results[1] as List<TopSeller>,
      );
    });
  }
}

final adminAnalyticsControllerProvider =
    AsyncNotifierProvider<AdminAnalyticsController, AdminAnalyticsState>(
        AdminAnalyticsController.new);

// ---------------------------------------------------------------------------
// Ops
// ---------------------------------------------------------------------------

class AdminOpsController extends AsyncNotifier<AdminOpsState> {
  @override
  Future<AdminOpsState> build() async {
    final api = ref.read(adminApiProvider);
    final retention = await api.getRetention();
    final version = await api.migrationVersion();
    return AdminOpsState(
      messageRetentionDays: retention,
      migrationVersion: version,
    );
  }

  Future<void> saveRetention(int days) async {
    await ref.read(adminApiProvider).setRetention(days);
    ref.invalidateSelf();
  }

  Future<int> runPurge() async {
    return ref.read(adminApiProvider).runPurge();
  }
}

final adminOpsControllerProvider =
    AsyncNotifierProvider<AdminOpsController, AdminOpsState>(
        AdminOpsController.new);
