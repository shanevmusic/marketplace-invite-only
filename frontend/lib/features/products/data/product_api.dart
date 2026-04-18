import 'package:dio/dio.dart';

import '../../../data/api/api_client.dart';
import 'product_dtos.dart';

class ProductApi {
  ProductApi(this._dio);
  final Dio _dio;

  Future<ProductListResponse> list({String? storeId, String? sellerId}) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/products',
        queryParameters: {
          if (storeId != null) 'store_id': storeId,
          if (sellerId != null) 'seller_id': sellerId,
        },
      );
      return ProductListResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ProductResponse> get(String productId) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/products/$productId');
      return ProductResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ProductResponse> create(CreateProductRequest body) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/products',
        data: body.toJson(),
      );
      return ProductResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<ProductResponse> update(String id, UpdateProductRequest body) async {
    try {
      final r = await _dio.patch<Map<String, dynamic>>(
        '/products/$id',
        data: body.toJson(),
      );
      return ProductResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> delete(String id) async {
    try {
      await _dio.delete<void>('/products/$id');
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
