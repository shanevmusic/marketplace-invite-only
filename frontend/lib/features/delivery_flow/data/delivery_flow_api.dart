import 'package:dio/dio.dart';

/// Thin API client for the Uber-style delivery flow endpoints (migration 0010).
class DeliveryFlowApi {
  DeliveryFlowApi(this._dio);
  final Dio _dio;

  Future<Map<String, dynamic>> driverAccept(String orderId) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/driver/orders/$orderId/accept',
    );
    return r.data ?? const {};
  }

  Future<void> driverLocation(
      String orderId, double lat, double lng) async {
    await _dio.post<void>(
      '/driver/orders/$orderId/location',
      data: {'lat': lat, 'lng': lng},
    );
  }

  Future<Map<String, dynamic>> driverRoute(String orderId) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/driver/orders/$orderId/route',
    );
    return r.data ?? const {};
  }

  Future<Map<String, dynamic>> driverComplete(
      String orderId, String code) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/driver/orders/$orderId/complete',
      data: {'code': code},
    );
    return r.data ?? const {};
  }

  Future<Map<String, dynamic>> customerEta(String orderId) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/customer/orders/$orderId/eta',
    );
    return r.data ?? const {};
  }

  Future<Map<String, dynamic>> customerCode(String orderId) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/customer/orders/$orderId/code',
    );
    return r.data ?? const {};
  }

  Future<List<Map<String, dynamic>>> listChat(String orderId) async {
    final r = await _dio.get<List<dynamic>>('/orders/$orderId/chat');
    return List<Map<String, dynamic>>.from(r.data ?? const []);
  }

  Future<Map<String, dynamic>> postChat(
      String orderId, String ciphertext, String nonce) async {
    final r = await _dio.post<Map<String, dynamic>>(
      '/orders/$orderId/chat',
      data: {'ciphertext': ciphertext, 'nonce': nonce},
    );
    return r.data ?? const {};
  }

  Future<List<Map<String, dynamic>>> adminTracking(String orderId) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/admin/orders/$orderId/tracking',
    );
    final points = r.data?['points'] as List<dynamic>? ?? const [];
    return List<Map<String, dynamic>>.from(points);
  }

  Future<List<Map<String, dynamic>>> adminMessages(String orderId) async {
    final r = await _dio.get<Map<String, dynamic>>(
      '/admin/orders/$orderId/messages',
    );
    final msgs = r.data?['messages'] as List<dynamic>? ?? const [];
    return List<Map<String, dynamic>>.from(msgs);
  }
}
