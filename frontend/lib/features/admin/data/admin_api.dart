import 'package:dio/dio.dart';

import '../../../data/api/api_client.dart';
import 'admin_dtos.dart';

class AdminApi {
  AdminApi(this._dio);
  final Dio _dio;

  // ------------------------------------------------------------------ users
  Future<AdminPagedUsers> listUsers({
    String? q,
    String? role,
    String? status,
    String? cursor,
    int limit = 25,
  }) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/admin/users',
        queryParameters: {
          if (q != null && q.isNotEmpty) 'q': q,
          if (role != null && role.isNotEmpty) 'role': role,
          if (status != null && status.isNotEmpty) 'status': status,
          if (cursor != null) 'cursor': cursor,
          'limit': limit,
        },
      );
      return AdminPagedUsers.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<AdminUserDetail> getUser(String id) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>('/admin/users/$id');
      return AdminUserDetail.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<AdminUserSummary> suspendUser(String id, String reason) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/admin/users/$id/suspend',
        data: {'reason': reason},
      );
      return AdminUserSummary.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<AdminUserSummary> unsuspendUser(String id) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/admin/users/$id/unsuspend',
      );
      return AdminUserSummary.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<AdminIssuedInvite> issueInvite({
    required String roleTarget,
    int expiresInDays = 7,
  }) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/admin/invites',
        data: {
          'role_target': roleTarget,
          'expires_in_days': expiresInDays,
        },
      );
      return AdminIssuedInvite.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // --------------------------------------------------------------- products
  Future<AdminPagedProducts> listProducts({
    String? q,
    String? status,
    String? sellerId,
    String? cursor,
    int limit = 25,
  }) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/admin/products',
        queryParameters: {
          if (q != null && q.isNotEmpty) 'q': q,
          if (status != null && status.isNotEmpty) 'status': status,
          if (sellerId != null) 'seller_id': sellerId,
          if (cursor != null) 'cursor': cursor,
          'limit': limit,
        },
      );
      return AdminPagedProducts.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<AdminProductSummary> disableProduct(String id, String reason) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/admin/products/$id/disable',
        data: {'reason': reason},
      );
      return AdminProductSummary.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<AdminProductSummary> restoreProduct(String id) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/admin/products/$id/restore',
      );
      return AdminProductSummary.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // -------------------------------------------------------------- analytics
  Future<AdminAnalyticsOverview> overview() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/admin/analytics/overview',
      );
      return AdminAnalyticsOverview.fromJson(r.data!);
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<List<TopSeller>> topSellers({int limit = 10}) async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/admin/analytics/top-sellers',
        queryParameters: {'limit': limit},
      );
      final data = (r.data!['data'] as List)
          .map((e) => TopSeller.fromJson(e as Map<String, dynamic>))
          .toList();
      return data;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  // --------------------------------------------------------------------- ops
  Future<int> getRetention() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/admin/ops/retention-config',
      );
      return (r.data!['message_retention_days'] as num).toInt();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<int> setRetention(int days) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/admin/ops/retention-config',
        data: {'message_retention_days': days},
      );
      return (r.data!['message_retention_days'] as num).toInt();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<int> runPurge() async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/admin/ops/purge-messages/run',
      );
      return (r.data!['purged_count'] as num).toInt();
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<String?> migrationVersion() async {
    try {
      final r = await _dio.get<Map<String, dynamic>>(
        '/admin/ops/migration-version',
      );
      return r.data!['version'] as String?;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}
