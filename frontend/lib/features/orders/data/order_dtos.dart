class DeliveryAddress {
  const DeliveryAddress({
    required this.line1,
    this.line2,
    required this.city,
    this.region,
    this.postal,
    required this.country,
    this.notes,
  });
  final String line1;
  final String? line2;
  final String city;
  final String? region;
  final String? postal;
  final String country;
  final String? notes;

  factory DeliveryAddress.fromJson(Map<String, dynamic> json) =>
      DeliveryAddress(
        line1: json['line1'] as String,
        line2: json['line2'] as String?,
        city: json['city'] as String,
        region: json['region'] as String?,
        postal: json['postal'] as String?,
        country: json['country'] as String,
        notes: json['notes'] as String?,
      );

  Map<String, dynamic> toJson() => {
        'line1': line1,
        if (line2 != null && line2!.isNotEmpty) 'line2': line2,
        'city': city,
        if (region != null && region!.isNotEmpty) 'region': region,
        if (postal != null && postal!.isNotEmpty) 'postal': postal,
        'country': country,
        if (notes != null && notes!.isNotEmpty) 'notes': notes,
      };

  String oneLine() {
    final parts = [line1, if (line2 != null && line2!.isNotEmpty) line2!, city];
    return parts.join(', ');
  }
}

class OrderItem {
  const OrderItem({
    required this.productId,
    required this.name,
    required this.quantity,
    required this.unitPriceMinor,
    required this.lineTotalMinor,
  });
  final String productId;
  final String name;
  final int quantity;
  final int unitPriceMinor;
  final int lineTotalMinor;

  factory OrderItem.fromJson(Map<String, dynamic> json) => OrderItem(
        productId: json['product_id'] as String,
        name: (json['name'] as String?) ?? '',
        quantity: json['quantity'] as int,
        unitPriceMinor: (json['unit_price_minor'] as int?) ?? 0,
        lineTotalMinor: (json['line_total_minor'] as int?) ?? 0,
      );
}

class OrderResponse {
  const OrderResponse({
    required this.id,
    required this.sellerId,
    required this.customerId,
    required this.status,
    required this.totalMinor,
    required this.currencyCode,
    required this.items,
    required this.deliveryAddress,
    required this.createdAt,
    this.storeName,
  });

  final String id;
  final String sellerId;
  final String customerId;
  final String status;
  final int totalMinor;
  final String currencyCode;
  final List<OrderItem> items;
  final DeliveryAddress deliveryAddress;
  final DateTime createdAt;
  final String? storeName;

  factory OrderResponse.fromJson(Map<String, dynamic> json) {
    final addr = json['delivery_address'] is Map
        ? DeliveryAddress.fromJson(
            (json['delivery_address'] as Map).cast<String, dynamic>())
        : const DeliveryAddress(line1: '', city: '', country: 'US');
    return OrderResponse(
      id: json['id'] as String,
      sellerId: json['seller_id'] as String,
      customerId: json['customer_id'] as String,
      status: json['status'] as String,
      totalMinor: (json['total_minor'] as int?) ?? 0,
      currencyCode: (json['currency_code'] as String?) ?? 'USD',
      items: (json['items'] as List<dynamic>? ?? [])
          .map((e) => OrderItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      deliveryAddress: addr,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
      storeName: json['store_name'] as String?,
    );
  }
}

class OrderListResponse {
  const OrderListResponse({required this.items});
  final List<OrderResponse> items;

  factory OrderListResponse.fromJson(Map<String, dynamic> json) =>
      OrderListResponse(
        items: (json['items'] as List<dynamic>? ?? [])
            .map((e) => OrderResponse.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class CreateOrderRequest {
  const CreateOrderRequest({required this.items, required this.deliveryAddress});
  final List<({String productId, int quantity})> items;
  final DeliveryAddress deliveryAddress;

  Map<String, dynamic> toJson() => {
        'items': items
            .map((e) => {'product_id': e.productId, 'quantity': e.quantity})
            .toList(),
        'delivery_address': deliveryAddress.toJson(),
      };
}
