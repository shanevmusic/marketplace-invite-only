class StoreResponse {
  const StoreResponse({
    required this.id,
    required this.sellerId,
    required this.name,
    required this.slug,
    required this.description,
    required this.city,
    required this.isActive,
    this.isPublic = false,
  });

  final String id;
  final String sellerId;
  final String name;
  final String slug;
  final String description;
  final String city;
  final bool isActive;
  final bool isPublic;

  factory StoreResponse.fromJson(Map<String, dynamic> json) => StoreResponse(
        id: json['id'] as String,
        sellerId: json['seller_id'] as String,
        name: json['name'] as String,
        slug: (json['slug'] as String?) ?? '',
        description: (json['description'] as String?) ?? '',
        city: json['city'] as String,
        isActive: (json['is_active'] as bool?) ?? true,
        isPublic: (json['is_public'] as bool?) ?? false,
      );
}

class CreateStoreRequest {
  const CreateStoreRequest({
    required this.name,
    required this.city,
    this.description,
    this.isPublic = false,
  });
  final String name;
  final String city;
  final String? description;
  final bool isPublic;

  Map<String, dynamic> toJson() => {
        'name': name,
        'city': city,
        if (description != null && description!.isNotEmpty)
          'description': description,
        'is_public': isPublic,
      };
}

class UpdateStoreRequest {
  const UpdateStoreRequest({
    this.name,
    this.city,
    this.description,
    this.isActive,
    this.isPublic,
  });
  final String? name;
  final String? city;
  final String? description;
  final bool? isActive;
  final bool? isPublic;

  Map<String, dynamic> toJson() => {
        if (name != null) 'name': name,
        if (city != null) 'city': city,
        if (description != null) 'description': description,
        if (isActive != null) 'is_active': isActive,
        if (isPublic != null) 'is_public': isPublic,
      };
}
