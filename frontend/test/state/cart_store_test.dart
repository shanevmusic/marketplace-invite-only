import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:flutter_secure_storage_platform_interface/flutter_secure_storage_platform_interface.dart';
import 'package:marketplace/features/cart/cart_store.dart';

/// In-memory replacement for flutter_secure_storage so unit tests don't hit
/// the platform channel.
class _InMemoryStorage extends FlutterSecureStoragePlatform {
  final Map<String, String> store = {};

  @override
  Future<bool> containsKey({
    required String key,
    required Map<String, String> options,
  }) async =>
      store.containsKey(key);

  @override
  Future<void> delete({
    required String key,
    required Map<String, String> options,
  }) async {
    store.remove(key);
  }

  @override
  Future<void> deleteAll({required Map<String, String> options}) async {
    store.clear();
  }

  @override
  Future<String?> read({
    required String key,
    required Map<String, String> options,
  }) async =>
      store[key];

  @override
  Future<Map<String, String>> readAll({
    required Map<String, String> options,
  }) async =>
      Map.from(store);

  @override
  Future<void> write({
    required String key,
    required String value,
    required Map<String, String> options,
  }) async {
    store[key] = value;
  }
}

void main() {
  late _InMemoryStorage mem;

  setUp(() {
    mem = _InMemoryStorage();
    FlutterSecureStoragePlatform.instance = mem;
  });

  ProviderContainer make() {
    final c = ProviderContainer();
    addTearDown(c.dispose);
    return c;
  }

  test('addLine creates a bucket and persists', () async {
    final c = make();
    await c.read(cartControllerProvider.future);
    await c.read(cartControllerProvider.notifier).addLine(
          sellerId: 's1',
          storeName: 'Store One',
          currencyCode: 'USD',
          line: const CartLine(
            productId: 'p1',
            name: 'Thing',
            unitPriceMinor: 500,
            quantity: 2,
          ),
        );
    final state = c.read(cartControllerProvider).value!;
    expect(state.totalItems, 2);
    expect(state.buckets['s1']!.subtotalMinor, 1000);
    expect(mem.store.containsKey(kCartStorageKey), isTrue);
  });

  test('adding the same product increments qty', () async {
    final c = make();
    await c.read(cartControllerProvider.future);
    final n = c.read(cartControllerProvider.notifier);
    final line = const CartLine(
      productId: 'p1',
      name: 'X',
      unitPriceMinor: 100,
      quantity: 1,
    );
    await n.addLine(
        sellerId: 's1', storeName: 'S', currencyCode: 'USD', line: line);
    await n.addLine(
        sellerId: 's1', storeName: 'S', currencyCode: 'USD', line: line);
    expect(c.read(cartControllerProvider).value!.totalItems, 2);
  });

  test('updateQuantity to zero removes the line', () async {
    final c = make();
    await c.read(cartControllerProvider.future);
    await c.read(cartControllerProvider.notifier).addLine(
          sellerId: 's1',
          storeName: 'S',
          currencyCode: 'USD',
          line: const CartLine(
            productId: 'p1',
            name: 'X',
            unitPriceMinor: 100,
            quantity: 3,
          ),
        );
    await c.read(cartControllerProvider.notifier).updateQuantity(
          sellerId: 's1',
          productId: 'p1',
          quantity: 0,
        );
    expect(c.read(cartControllerProvider).value!.buckets, isEmpty);
  });
}
