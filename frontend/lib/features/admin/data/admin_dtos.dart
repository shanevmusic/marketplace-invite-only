class AdminUserSummary {
  const AdminUserSummary({
    required this.id,
    required this.email,
    required this.displayName,
    required this.role,
    required this.status,
    required this.isActive,
    required this.createdAt,
    this.suspendedAt,
    this.suspendedReason,
  });

  final String id;
  final String email;
  final String displayName;
  final String role;
  final String status;
  final bool isActive;
  final DateTime createdAt;
  final DateTime? suspendedAt;
  final String? suspendedReason;

  factory AdminUserSummary.fromJson(Map<String, dynamic> j) => AdminUserSummary(
        id: j['id'] as String,
        email: j['email'] as String,
        displayName: j['display_name'] as String,
        role: j['role'] as String,
        status: j['status'] as String? ?? 'active',
        isActive: j['is_active'] as bool? ?? true,
        createdAt: DateTime.parse(j['created_at'] as String),
        suspendedAt: j['suspended_at'] != null
            ? DateTime.tryParse(j['suspended_at'] as String)
            : null,
        suspendedReason: j['suspended_reason'] as String?,
      );
}

class ReferralEdge {
  const ReferralEdge({
    required this.userId,
    required this.email,
    required this.displayName,
    required this.role,
    required this.createdAt,
  });
  final String userId;
  final String email;
  final String displayName;
  final String role;
  final DateTime createdAt;

  factory ReferralEdge.fromJson(Map<String, dynamic> j) => ReferralEdge(
        userId: j['user_id'] as String,
        email: j['email'] as String,
        displayName: j['display_name'] as String,
        role: j['role'] as String,
        createdAt: DateTime.parse(j['created_at'] as String),
      );
}

class AdminUserDetail {
  const AdminUserDetail({required this.user, this.referredBy, required this.referredUsers});
  final AdminUserSummary user;
  final ReferralEdge? referredBy;
  final List<ReferralEdge> referredUsers;

  factory AdminUserDetail.fromJson(Map<String, dynamic> j) => AdminUserDetail(
        user: AdminUserSummary.fromJson(j),
        referredBy: j['referred_by'] != null
            ? ReferralEdge.fromJson(j['referred_by'] as Map<String, dynamic>)
            : null,
        referredUsers: (j['referred_users'] as List? ?? [])
            .map((e) => ReferralEdge.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class AdminPagedUsers {
  const AdminPagedUsers({required this.data, required this.nextCursor});
  final List<AdminUserSummary> data;
  final String? nextCursor;

  factory AdminPagedUsers.fromJson(Map<String, dynamic> j) => AdminPagedUsers(
        data: (j['data'] as List)
            .map((e) => AdminUserSummary.fromJson(e as Map<String, dynamic>))
            .toList(),
        nextCursor: (j['pagination'] as Map<String, dynamic>?)?['next_cursor']
            as String?,
      );
}

class AdminProductSummary {
  const AdminProductSummary({
    required this.id,
    required this.sellerId,
    required this.storeId,
    required this.name,
    required this.priceMinor,
    required this.status,
    required this.isActive,
    required this.createdAt,
    this.stockQuantity,
    this.disabledAt,
    this.disabledReason,
  });

  final String id;
  final String sellerId;
  final String storeId;
  final String name;
  final int priceMinor;
  final int? stockQuantity;
  final String status;
  final bool isActive;
  final DateTime createdAt;
  final DateTime? disabledAt;
  final String? disabledReason;

  factory AdminProductSummary.fromJson(Map<String, dynamic> j) =>
      AdminProductSummary(
        id: j['id'] as String,
        sellerId: j['seller_id'] as String,
        storeId: j['store_id'] as String,
        name: j['name'] as String,
        priceMinor: (j['price_minor'] as num).toInt(),
        stockQuantity: j['stock_quantity'] as int?,
        status: j['status'] as String? ?? 'active',
        isActive: j['is_active'] as bool? ?? true,
        createdAt: DateTime.parse(j['created_at'] as String),
        disabledAt: j['disabled_at'] != null
            ? DateTime.tryParse(j['disabled_at'] as String)
            : null,
        disabledReason: j['disabled_reason'] as String?,
      );
}

class AdminPagedProducts {
  const AdminPagedProducts({required this.data, required this.nextCursor});
  final List<AdminProductSummary> data;
  final String? nextCursor;

  factory AdminPagedProducts.fromJson(Map<String, dynamic> j) =>
      AdminPagedProducts(
        data: (j['data'] as List)
            .map((e) => AdminProductSummary.fromJson(e as Map<String, dynamic>))
            .toList(),
        nextCursor: (j['pagination'] as Map<String, dynamic>?)?['next_cursor']
            as String?,
      );
}

class AdminAnalyticsOverview {
  const AdminAnalyticsOverview({
    required this.totalGmvMinor,
    required this.ordersCount,
    required this.activeUsers24h,
    required this.activeUsers7d,
    required this.activeUsers30d,
    required this.sellerCount,
    required this.customerCount,
    required this.driverCount,
    required this.adminCount,
  });

  final int totalGmvMinor;
  final int ordersCount;
  final int activeUsers24h;
  final int activeUsers7d;
  final int activeUsers30d;
  final int sellerCount;
  final int customerCount;
  final int driverCount;
  final int adminCount;

  factory AdminAnalyticsOverview.fromJson(Map<String, dynamic> j) =>
      AdminAnalyticsOverview(
        totalGmvMinor: (j['total_gmv_minor'] as num).toInt(),
        ordersCount: (j['orders_count'] as num).toInt(),
        activeUsers24h: (j['active_users_24h'] as num).toInt(),
        activeUsers7d: (j['active_users_7d'] as num).toInt(),
        activeUsers30d: (j['active_users_30d'] as num).toInt(),
        sellerCount: (j['seller_count'] as num).toInt(),
        customerCount: (j['customer_count'] as num).toInt(),
        driverCount: (j['driver_count'] as num).toInt(),
        adminCount: (j['admin_count'] as num).toInt(),
      );
}

class TopSeller {
  const TopSeller({
    required this.sellerId,
    required this.displayName,
    required this.lifetimeRevenueMinor,
    required this.lifetimeOrderCount,
  });
  final String sellerId;
  final String displayName;
  final int lifetimeRevenueMinor;
  final int lifetimeOrderCount;

  factory TopSeller.fromJson(Map<String, dynamic> j) => TopSeller(
        sellerId: j['seller_id'] as String,
        displayName: j['display_name'] as String,
        lifetimeRevenueMinor: (j['lifetime_revenue_minor'] as num).toInt(),
        lifetimeOrderCount: (j['lifetime_order_count'] as num).toInt(),
      );
}

class AdminIssuedInvite {
  const AdminIssuedInvite({
    required this.id,
    required this.token,
    required this.roleTarget,
    required this.createdAt,
    this.expiresAt,
  });
  final String id;
  final String token;
  final String? roleTarget;
  final DateTime createdAt;
  final DateTime? expiresAt;

  factory AdminIssuedInvite.fromJson(Map<String, dynamic> j) =>
      AdminIssuedInvite(
        id: j['id'] as String,
        token: j['token'] as String,
        roleTarget: j['role_target'] as String?,
        createdAt: DateTime.parse(j['created_at'] as String),
        expiresAt: j['expires_at'] != null
            ? DateTime.tryParse(j['expires_at'] as String)
            : null,
      );
}

class AdminOpsState {
  const AdminOpsState({
    required this.messageRetentionDays,
    required this.migrationVersion,
  });
  final int messageRetentionDays;
  final String? migrationVersion;
}
