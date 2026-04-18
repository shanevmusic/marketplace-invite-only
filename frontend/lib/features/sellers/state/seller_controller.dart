import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import '../data/seller_api.dart';
import '../data/seller_dtos.dart';

final sellerApiProvider = Provider<SellerApi>((ref) {
  return SellerApi(ref.watch(apiClientProvider));
});

class SellerDashboardController extends AsyncNotifier<SellerDashboardResponse> {
  @override
  Future<SellerDashboardResponse> build() async {
    return ref.read(sellerApiProvider).myDashboard();
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    state =
        await AsyncValue.guard(() => ref.read(sellerApiProvider).myDashboard());
  }
}

final sellerDashboardControllerProvider =
    AsyncNotifierProvider<SellerDashboardController, SellerDashboardResponse>(
        SellerDashboardController.new);

final sellerPublicByIdProvider =
    FutureProvider.family<SellerPublicResponse, String>((ref, id) async {
  return ref.read(sellerApiProvider).getPublic(id);
});
