import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

/// Client-only cart persisted in flutter_secure_storage under key `cart.v1`.
/// Each order = one seller/store (per-seller buckets).
class CartLine {
  const CartLine({
    required this.productId,
    required this.name,
    required this.unitPriceMinor,
    required this.quantity,
    this.imageKey,
    this.stockQuantity,
  });
  final String productId;
  final String name;
  final int unitPriceMinor;
  final int quantity;
  final String? imageKey;
  final int? stockQuantity;

  int get lineTotalMinor => unitPriceMinor * quantity;

  CartLine copyWith({int? quantity}) => CartLine(
        productId: productId,
        name: name,
        unitPriceMinor: unitPriceMinor,
        quantity: quantity ?? this.quantity,
        imageKey: imageKey,
        stockQuantity: stockQuantity,
      );

  Map<String, dynamic> toJson() => {
        'product_id': productId,
        'name': name,
        'unit_price_minor': unitPriceMinor,
        'quantity': quantity,
        if (imageKey != null) 'image_key': imageKey,
        if (stockQuantity != null) 'stock_quantity': stockQuantity,
      };

  factory CartLine.fromJson(Map<String, dynamic> json) => CartLine(
        productId: json['product_id'] as String,
        name: (json['name'] as String?) ?? '',
        unitPriceMinor: (json['unit_price_minor'] as int?) ?? 0,
        quantity: (json['quantity'] as int?) ?? 1,
        imageKey: json['image_key'] as String?,
        stockQuantity: json['stock_quantity'] as int?,
      );
}

class SellerCart {
  const SellerCart({
    required this.sellerId,
    required this.storeName,
    required this.currencyCode,
    required this.lines,
  });
  final String sellerId;
  final String storeName;
  final String currencyCode;
  final List<CartLine> lines;

  int get subtotalMinor => lines.fold<int>(0, (s, l) => s + l.lineTotalMinor);
  int get itemCount => lines.fold<int>(0, (s, l) => s + l.quantity);

  SellerCart copyWith({List<CartLine>? lines, String? storeName}) => SellerCart(
        sellerId: sellerId,
        storeName: storeName ?? this.storeName,
        currencyCode: currencyCode,
        lines: lines ?? this.lines,
      );

  Map<String, dynamic> toJson() => {
        'seller_id': sellerId,
        'store_name': storeName,
        'currency_code': currencyCode,
        'lines': lines.map((e) => e.toJson()).toList(),
      };

  factory SellerCart.fromJson(Map<String, dynamic> json) => SellerCart(
        sellerId: json['seller_id'] as String,
        storeName: (json['store_name'] as String?) ?? '',
        currencyCode: (json['currency_code'] as String?) ?? 'USD',
        lines: (json['lines'] as List<dynamic>? ?? [])
            .map((e) => CartLine.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class CartState {
  const CartState({required this.buckets});
  final Map<String, SellerCart> buckets;

  int get totalItems => buckets.values.fold<int>(0, (s, b) => s + b.itemCount);

  Map<String, dynamic> toJson() =>
      {'v': 1, 'buckets': buckets.map((k, v) => MapEntry(k, v.toJson()))};

  factory CartState.empty() => const CartState(buckets: {});

  factory CartState.fromJson(Map<String, dynamic> json) {
    final raw = (json['buckets'] as Map?)?.cast<String, dynamic>() ?? {};
    return CartState(
      buckets: {
        for (final e in raw.entries)
          e.key: SellerCart.fromJson((e.value as Map).cast<String, dynamic>()),
      },
    );
  }
}

const String kCartStorageKey = 'cart.v1';

class CartController extends AsyncNotifier<CartState> {
  FlutterSecureStorage? _storageOverride;

  void setStorage(FlutterSecureStorage s) => _storageOverride = s;

  FlutterSecureStorage get _storage =>
      _storageOverride ?? const FlutterSecureStorage();

  @override
  Future<CartState> build() async {
    try {
      final raw = await _storage.read(key: kCartStorageKey);
      if (raw == null || raw.isEmpty) return CartState.empty();
      final map = jsonDecode(raw) as Map<String, dynamic>;
      return CartState.fromJson(map);
    } catch (_) {
      return CartState.empty();
    }
  }

  Future<void> _persist(CartState s) async {
    await _storage.write(key: kCartStorageKey, value: jsonEncode(s.toJson()));
    state = AsyncValue.data(s);
  }

  Future<void> addLine({
    required String sellerId,
    required String storeName,
    required String currencyCode,
    required CartLine line,
  }) async {
    final current = state.value ?? CartState.empty();
    final bucket = current.buckets[sellerId] ??
        SellerCart(
          sellerId: sellerId,
          storeName: storeName,
          currencyCode: currencyCode,
          lines: const [],
        );
    final existingIdx =
        bucket.lines.indexWhere((l) => l.productId == line.productId);
    List<CartLine> nextLines;
    if (existingIdx >= 0) {
      final existing = bucket.lines[existingIdx];
      nextLines = [...bucket.lines];
      nextLines[existingIdx] =
          existing.copyWith(quantity: existing.quantity + line.quantity);
    } else {
      nextLines = [...bucket.lines, line];
    }
    final nextBucket = bucket.copyWith(lines: nextLines, storeName: storeName);
    final nextBuckets = {...current.buckets, sellerId: nextBucket};
    await _persist(CartState(buckets: nextBuckets));
  }

  Future<void> updateQuantity({
    required String sellerId,
    required String productId,
    required int quantity,
  }) async {
    final current = state.value ?? CartState.empty();
    final bucket = current.buckets[sellerId];
    if (bucket == null) return;
    final lines = [...bucket.lines];
    final idx = lines.indexWhere((l) => l.productId == productId);
    if (idx < 0) return;
    if (quantity <= 0) {
      lines.removeAt(idx);
    } else {
      lines[idx] = lines[idx].copyWith(quantity: quantity);
    }
    final nextBuckets = Map<String, SellerCart>.from(current.buckets);
    if (lines.isEmpty) {
      nextBuckets.remove(sellerId);
    } else {
      nextBuckets[sellerId] = bucket.copyWith(lines: lines);
    }
    await _persist(CartState(buckets: nextBuckets));
  }

  Future<void> removeLine({
    required String sellerId,
    required String productId,
  }) async =>
      updateQuantity(sellerId: sellerId, productId: productId, quantity: 0);

  Future<void> clearBucket(String sellerId) async {
    final current = state.value ?? CartState.empty();
    final next = Map<String, SellerCart>.from(current.buckets)
      ..remove(sellerId);
    await _persist(CartState(buckets: next));
  }

  Future<void> clearAll() async {
    await _storage.delete(key: kCartStorageKey);
    state = AsyncValue.data(CartState.empty());
  }
}

final cartControllerProvider =
    AsyncNotifierProvider<CartController, CartState>(CartController.new);
