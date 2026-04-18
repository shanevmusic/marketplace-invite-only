import 'package:dio/dio.dart';

import '../../../data/api/api_client.dart';
import 'order_dtos.dart';

class OrderApi {
  OrderApi(this._dio);
  final Dio _dio;

  Future<OrderListResponse> list({String? role, String? status}) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/orders',
        queryParameters: {
          if (role != null) 'role': role,
          if (status != null) 'status': status,
        },
      );
      return OrderListResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<OrderResponse> get(String orderId) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/orders/$orderId');
      return OrderResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<OrderResponse> create(CreateOrderRequest body) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/orders',
        data: body.toJson(),
      );
      return OrderResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<OrderResponse> transition(String orderId, String action) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/orders/$orderId/$action',
      );
      return OrderResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
