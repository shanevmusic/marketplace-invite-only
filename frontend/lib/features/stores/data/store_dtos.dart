class StoreResponse {
  const StoreResponse({
    required this.id,
    required this.sellerId,
    required this.name,
    required this.slug,
    required this.description,
    required this.city,
    required this.isActive,
  });

  final String id;
  final String sellerId;
  final String name;
  final String slug;
  final String description;
  final String city;
  final bool isActive;

  factory StoreResponse.fromJson(Map<String, dynamic> json) => StoreResponse(
        id: json['id'] as String,
        sellerId: json['seller_id'] as String,
        name: json['name'] as String,
        slug: (json['slug'] as String?) ?? '',
        description: (json['description'] as String?) ?? '',
        city: json['city'] as String,
        isActive: (json['is_active'] as bool?) ?? true,
      );
}

class CreateStoreRequest {
  const CreateStoreRequest({
    required this.name,
    required this.city,
    this.description,
  });
  final String name;
  final String city;
  final String? description;

  Map<String, dynamic> toJson() => {
        'name': name,
        'city': city,
        if (description != null && description!.isNotEmpty)
          'description': description,
      };
}

class UpdateStoreRequest {
  const UpdateStoreRequest({
    this.name,
    this.city,
    this.description,
    this.isActive,
  });
  final String? name;
  final String? city;
  final String? description;
  final bool? isActive;

  Map<String, dynamic> toJson() => {
        if (name != null) 'name': name,
        if (city != null) 'city': city,
        if (description != null) 'description': description,
        if (isActive != null) 'is_active': isActive,
      };
}
