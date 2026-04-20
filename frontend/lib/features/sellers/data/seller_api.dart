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

  /// Returns the active seller_referral invite (creating one if needed).
  /// Idempotent — same token until regenerated.
  Future<SellerInvite> getOrCreateReferral() async {
    try {
      final r = await _dio.post<Map<String, dynamic>>('/invites/seller_referral');
      return SellerInvite.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  /// Revokes the current seller_referral and issues a new one.
  Future<SellerInvite> regenerateReferral() async {
    try {
      final r =
          await _dio.post<Map<String, dynamic>>('/invites/seller_referral/regenerate');
      return SellerInvite.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
