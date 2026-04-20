import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';
import '../data/delivery_flow_api.dart';

final deliveryFlowApiProvider = Provider<DeliveryFlowApi>((ref) {
  return DeliveryFlowApi(ref.watch(apiClientProvider));
});

/// Polls `/customer/orders/:id/eta` — coordinate-free (ADR-0014).
final customerEtaProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, orderId) async {
  return ref.watch(deliveryFlowApiProvider).customerEta(orderId);
});

final customerCodeProvider =
    FutureProvider.family<Map<String, dynamic>, String>((ref, orderId) async {
  return ref.watch(deliveryFlowApiProvider).customerCode(orderId);
});

final orderChatProvider =
    FutureProvider.family<List<Map<String, dynamic>>, String>(
        (ref, orderId) async {
  return ref.watch(deliveryFlowApiProvider).listChat(orderId);
});

final adminTrackingProvider =
    FutureProvider.family<List<Map<String, dynamic>>, String>(
        (ref, orderId) async {
  return ref.watch(deliveryFlowApiProvider).adminTracking(orderId);
});

final adminMessagesProvider =
    FutureProvider.family<List<Map<String, dynamic>>, String>(
        (ref, orderId) async {
  return ref.watch(deliveryFlowApiProvider).adminMessages(orderId);
});
