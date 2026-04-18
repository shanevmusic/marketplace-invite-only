import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import '../data/store_api.dart';
import '../data/store_dtos.dart';

final storeApiProvider = Provider<StoreApi>((ref) {
  return StoreApi(ref.watch(apiClientProvider));
});

class MyStoreController extends AsyncNotifier<StoreResponse?> {
  @override
  Future<StoreResponse?> build() async {
    final api = ref.read(storeApiProvider);
    return api.getMyStore();
  }

  Future<void> create(CreateStoreRequest body) async {
    state = const AsyncValue.loading();
    final api = ref.read(storeApiProvider);
    state = await AsyncValue.guard(() => api.create(body));
  }

  Future<void> updateStore(UpdateStoreRequest body) async {
    state = const AsyncValue.loading();
    final api = ref.read(storeApiProvider);
    state = await AsyncValue.guard(() => api.update(body));
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    final api = ref.read(storeApiProvider);
    state = await AsyncValue.guard(() => api.getMyStore());
  }
}

final myStoreControllerProvider =
    AsyncNotifierProvider<MyStoreController, StoreResponse?>(
        MyStoreController.new);

/// Seller-public store lookup by id (for customer seller detail screen).
final storeByIdProvider =
    FutureProvider.family<StoreResponse, String>((ref, id) async {
  return ref.read(storeApiProvider).getById(id);
});
