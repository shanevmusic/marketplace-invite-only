class SellerPublicResponse {
  const SellerPublicResponse({
    required this.id,
    required this.displayName,
    this.bio,
    this.city,
  });
  final String id;
  final String displayName;
  final String? bio;
  final String? city;

  factory SellerPublicResponse.fromJson(Map<String, dynamic> json) =>
      SellerPublicResponse(
        id: json['id'] as String,
        displayName: (json['display_name'] as String?) ?? '',
        bio: json['bio'] as String?,
        city: json['city'] as String?,
      );
}

class SellerDashboardResponse {
  const SellerDashboardResponse({
    required this.sellerId,
    required this.lifetimeSalesMinor,
    required this.lifetimeOrdersCount,
    required this.activeOrdersCount,
    required this.currencyCode,
    this.lastUpdated,
  });
  final String sellerId;
  final int lifetimeSalesMinor;
  final int lifetimeOrdersCount;
  final int activeOrdersCount;
  final String currencyCode;
  final DateTime? lastUpdated;

  factory SellerDashboardResponse.fromJson(Map<String, dynamic> json) =>
      SellerDashboardResponse(
        sellerId: json['seller_id'] as String,
        lifetimeSalesMinor: (json['lifetime_sales_amount'] as int?) ??
            (json['lifetime_sales_minor'] as int?) ??
            0,
        lifetimeOrdersCount: (json['lifetime_orders_count'] as int?) ?? 0,
        activeOrdersCount: (json['active_orders_count'] as int?) ?? 0,
        currencyCode: (json['currency_code'] as String?) ?? 'USD',
        lastUpdated: json['last_updated'] != null
            ? DateTime.tryParse(json['last_updated'] as String)
            : null,
      );
}
