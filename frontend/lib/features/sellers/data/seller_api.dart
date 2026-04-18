import 'package:dio/dio.dart';

import '../../../data/api/api_client.dart';
import 'seller_dtos.dart';

class SellerApi {
  SellerApi(this._dio);
  final Dio _dio;

  Future<SellerPublicResponse> getPublic(String sellerId) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/sellers/$sellerId');
      return SellerPublicResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<SellerDashboardResponse> myDashboard() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/sellers/me/dashboard');
      return SellerDashboardResponse.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
