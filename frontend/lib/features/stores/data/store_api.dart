import 'package:dio/dio.dart';

import '../../../data/api/api_client.dart';
import 'store_dtos.dart';

class StoreApi {
  StoreApi(this._dio);
  final Dio _dio;

  Future<StoreResponse?> getMyStore() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/stores/me');
      return StoreResponse.fromJson(r.data!);
    } on DioException catch (e) {
      if (e.response?.statusCode == 404) return null;
      throw ApiException.fromDio(e);
    }
  }

  Future<StoreResponse> create(CreateStoreRequest body) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/stores',
        data: body.toJson(),
      );
      return StoreResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<StoreResponse> update(UpdateStoreRequest body) async {
    try {
      final r = await _dio.patch<Map<String, dynamic>>(
        '/stores/me',
        data: body.toJson(),
      );
      return StoreResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<StoreResponse> getById(String storeId) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/stores/$storeId');
      return StoreResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
