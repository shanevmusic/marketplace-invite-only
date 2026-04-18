import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/data/api/api_client.dart';
import 'package:marketplace/features/stores/data/store_api.dart';
import 'package:marketplace/features/stores/data/store_dtos.dart';
import 'package:marketplace/features/stores/state/store_controller.dart';

class MockStoreApi extends Mock implements StoreApi {}

void main() {
  setUpAll(() {
    registerFallbackValue(
      const CreateStoreRequest(name: '', city: ''),
    );
  });

  late MockStoreApi api;

  setUp(() {
    api = MockStoreApi();
  });

  ProviderContainer make() {
    final c = ProviderContainer(
      overrides: [storeApiProvider.overrideWithValue(api)],
    );
    addTearDown(c.dispose);
    return c;
  }

  const sample = StoreResponse(
    id: 's1',
    sellerId: 'u1',
    name: 'Acme',
    slug: 'acme',
    description: '',
    city: 'Portland',
    isActive: true,
  );

  test('build returns null when seller has no store', () async {
    when(() => api.getMyStore()).thenAnswer((_) async => null);
    final c = make();
    final v = await c.read(myStoreControllerProvider.future);
    expect(v, isNull);
  });

  test('create sets state to the new store', () async {
    when(() => api.getMyStore()).thenAnswer((_) async => null);
    when(() => api.create(any())).thenAnswer((_) async => sample);
    final c = make();
    await c.read(myStoreControllerProvider.future);
    await c
        .read(myStoreControllerProvider.notifier)
        .create(const CreateStoreRequest(name: 'Acme', city: 'Portland'));
    expect(c.read(myStoreControllerProvider).value, sample);
  });

  test('create surfaces STORE_ALREADY_EXISTS as error', () async {
    when(() => api.getMyStore()).thenAnswer((_) async => null);
    when(() => api.create(any())).thenThrow(
      ApiException(statusCode: 409, code: 'STORE_ALREADY_EXISTS'),
    );
    final c = make();
    await c.read(myStoreControllerProvider.future);
    await c
        .read(myStoreControllerProvider.notifier)
        .create(const CreateStoreRequest(name: 'Acme', city: 'PDX'));
    final s = c.read(myStoreControllerProvider);
    expect(s.hasError, isTrue);
    expect(s.error, isA<ApiException>());
    expect((s.error as ApiException).isStoreAlreadyExists, isTrue);
  });
}
