import '../../products/data/product_dtos.dart';
import '../../sellers/data/seller_dtos.dart';

/// ADR-0007 sealed state for the Discover screen. An Unreferred customer
/// never causes a /products call.
sealed class CustomerDiscoverState {
  const CustomerDiscoverState();
}

/// No referring seller on the auth session — blocker empty state, no network.
class DiscoverUnreferred extends CustomerDiscoverState {
  const DiscoverUnreferred();
}

class DiscoverLoading extends CustomerDiscoverState {
  const DiscoverLoading();
}

/// Referring seller public profile could not be loaded (404).
class DiscoverSellerProfileMissing extends CustomerDiscoverState {
  const DiscoverSellerProfileMissing({required this.sellerId});
  final String sellerId;
}

/// Seller exists but has no products.
class DiscoverNoProducts extends CustomerDiscoverState {
  const DiscoverNoProducts({required this.seller});
  final SellerPublicResponse seller;
}

class DiscoverReady extends CustomerDiscoverState {
  const DiscoverReady({required this.seller, required this.products});
  final SellerPublicResponse seller;
  final List<ProductResponse> products;
}

class DiscoverError extends CustomerDiscoverState {
  const DiscoverError(this.message);
  final String message;
}
