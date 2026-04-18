class ProductImage {
  const ProductImage({required this.s3Key, required this.displayOrder});
  final String s3Key;
  final int displayOrder;

  factory ProductImage.fromJson(Map<String, dynamic> json) => ProductImage(
        s3Key: json['s3_key'] as String,
        displayOrder: (json['display_order'] as int?) ?? 0,
      );

  Map<String, dynamic> toJson() => {
        's3_key': s3Key,
        'display_order': displayOrder,
      };
}

class ProductResponse {
  const ProductResponse({
    required this.id,
    required this.storeId,
    required this.sellerId,
    required this.name,
    required this.description,
    required this.priceMinor,
    required this.currencyCode,
    required this.stockQuantity,
    required this.isActive,
    required this.images,
  });

  final String id;
  final String storeId;
  final String sellerId;
  final String name;
  final String description;
  final int priceMinor;
  final String currencyCode;
  final int stockQuantity;
  final bool isActive;
  final List<ProductImage> images;

  String? get primaryImageKey => images.isEmpty ? null : images.first.s3Key;

  factory ProductResponse.fromJson(Map<String, dynamic> json) {
    final imgs = (json['images'] as List<dynamic>? ?? [])
        .map((e) => ProductImage.fromJson(e as Map<String, dynamic>))
        .toList()
      ..sort((a, b) => a.displayOrder.compareTo(b.displayOrder));
    return ProductResponse(
      id: json['id'] as String,
      storeId: json['store_id'] as String,
      sellerId: json['seller_id'] as String,
      name: json['name'] as String,
      description: (json['description'] as String?) ?? '',
      priceMinor: json['price_minor'] as int,
      currencyCode: (json['currency_code'] as String?) ?? 'USD',
      stockQuantity: (json['stock_quantity'] as int?) ?? 0,
      isActive: (json['is_active'] as bool?) ?? true,
      images: imgs,
    );
  }
}

class ProductListResponse {
  const ProductListResponse({required this.items});
  final List<ProductResponse> items;

  factory ProductListResponse.fromJson(Map<String, dynamic> json) =>
      ProductListResponse(
        items: (json['items'] as List<dynamic>? ?? [])
            .map((e) => ProductResponse.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class CreateProductRequest {
  const CreateProductRequest({
    this.storeId,
    required this.name,
    this.description,
    required this.priceMinor,
    this.stockQuantity,
    this.images = const [],
  });
  final String? storeId;
  final String name;
  final String? description;
  final int priceMinor;
  final int? stockQuantity;
  final List<ProductImage> images;

  Map<String, dynamic> toJson() => {
        if (storeId != null) 'store_id': storeId,
        'name': name,
        if (description != null && description!.isNotEmpty)
          'description': description,
        'price_minor': priceMinor,
        if (stockQuantity != null) 'stock_quantity': stockQuantity,
        'images': images.map((e) => e.toJson()).toList(),
      };
}

class UpdateProductRequest {
  const UpdateProductRequest({
    this.name,
    this.description,
    this.priceMinor,
    this.stockQuantity,
    this.isActive,
    this.images,
  });
  final String? name;
  final String? description;
  final int? priceMinor;
  final int? stockQuantity;
  final bool? isActive;
  final List<ProductImage>? images;

  Map<String, dynamic> toJson() => {
        if (name != null) 'name': name,
        if (description != null) 'description': description,
        if (priceMinor != null) 'price_minor': priceMinor,
        if (stockQuantity != null) 'stock_quantity': stockQuantity,
        if (isActive != null) 'is_active': isActive,
        if (images != null)
          'images': images!.map((e) => e.toJson()).toList(),
      };
}
