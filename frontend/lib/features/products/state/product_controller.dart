import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import '../data/product_api.dart';
import '../data/product_dtos.dart';

final productApiProvider = Provider<ProductApi>((ref) {
  return ProductApi(ref.watch(apiClientProvider));
});

/// Seller's own products (by seller_id inferred server-side via auth).
class MyProductsController
    extends AsyncNotifier<List<ProductResponse>> {
  @override
  Future<List<ProductResponse>> build() async {
    final api = ref.read(productApiProvider);
    final r = await api.list();
    return r.items;
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state = await AsyncValue.guard(() async {
      final r = await ref.read(productApiProvider).list();
      return r.items;
    });
  }

  Future<ProductResponse> create(CreateProductRequest body) async {
    final p = await ref.read(productApiProvider).create(body);
    final current = state.value ?? [];
    state = AsyncValue.data([...current, p]);
    return p;
  }

  Future<ProductResponse> updateProduct(
      String id, UpdateProductRequest body) async {
    final p = await ref.read(productApiProvider).update(id, body);
    final current = state.value ?? [];
    state = AsyncValue.data([
      for (final x in current)
        if (x.id == id) p else x,
    ]);
    return p;
  }

  Future<void> delete(String id) async {
    await ref.read(productApiProvider).delete(id);
    final current = state.value ?? [];
    state = AsyncValue.data([
      for (final x in current)
        if (x.id != id) x
    ]);
  }
}

final myProductsControllerProvider =
    AsyncNotifierProvider<MyProductsController, List<ProductResponse>>(
        MyProductsController.new);

/// Customer-facing list by seller id.
final productsBySellerProvider =
    FutureProvider.family<List<ProductResponse>, String>(
        (ref, sellerId) async {
  final r = await ref.read(productApiProvider).list(sellerId: sellerId);
  return r.items;
});

/// Single product lookup.
final productByIdProvider =
    FutureProvider.family<ProductResponse, String>((ref, id) async {
  return ref.read(productApiProvider).get(id);
});
