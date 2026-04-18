// Verifies the ADR-0007 sealed state contract: an Unreferred customer never
// causes a /products or /sellers call.
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/features/auth/data/auth_dtos.dart';
import 'package:marketplace/features/auth/data/auth_repository.dart';
import 'package:marketplace/features/auth/state/auth_controller.dart';
import 'package:marketplace/features/discover/state/discover_controller.dart';
import 'package:marketplace/features/discover/state/discover_state.dart';
import 'package:marketplace/features/products/data/product_api.dart';
import 'package:marketplace/features/products/data/product_dtos.dart';
import 'package:marketplace/features/products/state/product_controller.dart';
import 'package:marketplace/features/sellers/data/seller_api.dart';
import 'package:marketplace/features/sellers/data/seller_dtos.dart';
import 'package:marketplace/features/sellers/state/seller_controller.dart';

class MockSellerApi extends Mock implements SellerApi {}

class MockProductApi extends Mock implements ProductApi {}

class _StubAuthRepo extends Mock implements AuthRepository {}

AuthSession _session(String? referringSellerId) => AuthSession(
      user: AuthUser(
        id: 'u1',
        email: 'a@b.c',
        role: 'customer',
        displayName: 'A',
        referringSellerId: referringSellerId,
      ),
      accessToken: 'a',
      refreshToken: 'r',
    );

void main() {
  late MockSellerApi sellerApi;
  late MockProductApi productApi;
  late _StubAuthRepo repo;

  setUp(() {
    sellerApi = MockSellerApi();
    productApi = MockProductApi();
    repo = _StubAuthRepo();
    when(() => repo.setSessionExpiredListener(any())).thenReturn(null);
    when(() => repo.seedFromStorage()).thenAnswer((_) async => null);
  });

  ProviderContainer containerFor(AuthSession? session) {
    final container = ProviderContainer(
      overrides: [
        authRepositoryProvider.overrideWithValue(repo),
        sellerApiProvider.overrideWithValue(sellerApi),
        productApiProvider.overrideWithValue(productApi),
        authControllerProvider.overrideWith(() => _FakeAuthController(session)),
      ],
    );
    addTearDown(container.dispose);
    return container;
  }

  test('Unreferred → no /sellers or /products call, returns DiscoverUnreferred',
      () async {
    final c = containerFor(_session(null));
    // Prime the auth controller so DiscoverController sees a data state.
    await c.read(authControllerProvider.future);
    final state = await c.read(discoverControllerProvider.future);
    expect(state, isA<DiscoverUnreferred>());
    verifyZeroInteractions(productApi);
    verifyZeroInteractions(sellerApi);
  });

  test('Referred + products → DiscoverReady with items', () async {
    when(() => sellerApi.getPublic('s1')).thenAnswer(
      (_) async => const SellerPublicResponse(id: 's1', displayName: 'Store'),
    );
    when(() => productApi.list(sellerId: 's1')).thenAnswer(
      (_) async => ProductListResponse(items: [
        const ProductResponse(
          id: 'p1',
          storeId: 'st1',
          sellerId: 's1',
          name: 'Widget',
          description: '',
          priceMinor: 1299,
          currencyCode: 'USD',
          stockQuantity: 10,
          isActive: true,
          images: [],
        ),
      ]),
    );
    final c = containerFor(_session('s1'));
    await c.read(authControllerProvider.future);
    final state = await c.read(discoverControllerProvider.future);
    expect(state, isA<DiscoverReady>());
  });
}

class _FakeAuthController extends AuthController {
  _FakeAuthController(this._session);
  final AuthSession? _session;

  @override
  Future<AuthSession?> build() async => _session;
}
