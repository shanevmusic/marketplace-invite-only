import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../data/api/api_client.dart';

/// Phase 12 — S3 presigned upload flow: presign → PUT → confirm.
///
/// The backend returns a short-lived (5 min) presigned PUT URL plus the
/// eventual CDN URL after `confirm` verifies the object exists.
class ProductImageService {
  ProductImageService(this._dio);
  final Dio _dio;

  /// Uploads [bytes] and returns the public CDN URL to persist on the product.
  Future<String> uploadProductImage({
    required Uint8List bytes,
    required String filename,
    required String contentType,
  }) async {
    final presign = await _presign(
      purpose: 'product_image',
      filename: filename,
      contentType: contentType,
    );
    await _putToS3(
      url: presign.url,
      bytes: bytes,
      contentType: contentType,
    );
    return _confirm(s3Key: presign.s3Key);
  }

  Future<_PresignResult> _presign({
    required String purpose,
    required String filename,
    required String contentType,
  }) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/uploads/presign',
        data: {
          'purpose': purpose,
          'filename': filename,
          'content_type': contentType,
        },
      );
      final data = r.data!;
      return _PresignResult(
        url: data['url'] as String,
        s3Key: data['s3_key'] as String,
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<void> _putToS3({
    required String url,
    required Uint8List bytes,
    required String contentType,
  }) async {
    // Presigned PUT bypasses our auth interceptor — use a bare Dio.
    final bare = Dio();
    try {
      await bare.put<void>(
        url,
        data: Stream<List<int>>.fromIterable([bytes]),
        options: Options(
          headers: {
            'Content-Type': contentType,
            'Content-Length': bytes.length,
          },
        ),
      );
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }

  Future<String> _confirm({required String s3Key}) async {
    try {
      final r = await _dio.post<Map<String, dynamic>>(
        '/uploads/confirm',
        data: {'s3_key': s3Key},
      );
      return r.data!['url'] as String;
    } on DioException catch (e) {
      throw ApiException.fromDio(e);
    }
  }
}

class _PresignResult {
  _PresignResult({required this.url, required this.s3Key});
  final String url;
  final String s3Key;
}

final productImageServiceProvider = Provider<ProductImageService>((ref) {
  return ProductImageService(ref.watch(apiClientProvider));
});
