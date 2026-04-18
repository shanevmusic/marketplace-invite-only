import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import '../../auth/state/auth_controller.dart';
import '../../products/state/product_controller.dart';
import '../../sellers/state/seller_controller.dart';
import 'discover_state.dart';

class DiscoverController extends AsyncNotifier<CustomerDiscoverState> {
  @override
  Future<CustomerDiscoverState> build() async {
    final session = ref.watch(authControllerProvider).valueOrNull;
    final sellerId = session?.user.referringSellerId;
    if (sellerId == null || sellerId.isEmpty) {
      // ADR-0007: Unreferred customers never call /products.
      return const DiscoverUnreferred();
    }
    try {
      final seller = await ref.read(sellerApiProvider).getPublic(sellerId);
      final products =
          await ref.read(productApiProvider).list(sellerId: sellerId);
      if (products.items.isEmpty) {
        return DiscoverNoProducts(seller: seller);
      }
      return DiscoverReady(seller: seller, products: products.items);
    } on ApiException catch (e) {
      if (e.isNotFound) {
        return DiscoverSellerProfileMissing(sellerId: sellerId);
      }
      return DiscoverError(e.message ?? 'Something went wrong');
    } catch (_) {
      return const DiscoverError('Something went wrong');
    }
  }

  Future<void> refresh() async {
    state = const AsyncValue.loading();
    ref.invalidateSelf();
  }
}

final discoverControllerProvider =
    AsyncNotifierProvider<DiscoverController, CustomerDiscoverState>(
        DiscoverController.new);
