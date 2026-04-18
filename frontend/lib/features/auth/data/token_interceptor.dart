import 'dart:async';

import 'package:dio/dio.dart';

import 'auth_dtos.dart';

/// Dio interceptor that:
/// - attaches the current access token to every outbound request,
/// - on 401 (non-refresh, not already retried) calls [onRefresh] exactly once
///   and retries the original request with the new access token.
/// - on refresh failure, calls [onSessionExpired] and surfaces the 401 to the
///   caller.
///
/// A single in-flight refresh is shared via [_completer] so N concurrent 401s
/// collapse to one refresh call (Flow 9).
class TokenInterceptor extends Interceptor {
  TokenInterceptor({
    required this.readAccess,
    required this.readRefresh,
    required this.onRefresh,
    required this.onSessionExpired,
    required this.retryDio,
  });

  /// Supplies the current access token (nullable when logged out).
  final String? Function() readAccess;
  final String? Function() readRefresh;

  /// Should call AuthApi.refresh, persist the new pair, and return the new
  /// access token. Throw AuthApiException on failure.
  final Future<String> Function() onRefresh;

  final void Function() onSessionExpired;

  /// A Dio instance used to retry the original request after refresh. Usually
  /// the same Dio the interceptor is attached to.
  final Dio retryDio;

  Completer<String>? _completer;

  static const _retryFlag = 'x-token-retry';

  @override
  void onRequest(RequestOptions options, RequestInterceptorHandler handler) {
    final access = readAccess();
    if (access != null && !options.headers.containsKey('Authorization')) {
      options.headers['Authorization'] = 'Bearer $access';
    }
    handler.next(options);
  }

  @override
  Future<void> onError(
    DioException err,
    ErrorInterceptorHandler handler,
  ) async {
    final res = err.response;
    final opts = err.requestOptions;
    final isAuthEndpoint = opts.path.contains('/auth/refresh') ||
        opts.path.contains('/auth/login') ||
        opts.path.contains('/auth/signup');
    if (res?.statusCode != 401 ||
        isAuthEndpoint ||
        opts.extra[_retryFlag] == true ||
        readRefresh() == null) {
      return handler.next(err);
    }

    try {
      final newAccess = await _refreshOnce();
      final retryOpts = Options(
        method: opts.method,
        headers: {...opts.headers, 'Authorization': 'Bearer $newAccess'},
        contentType: opts.contentType,
        responseType: opts.responseType,
        extra: {...opts.extra, _retryFlag: true},
      );
      final response = await retryDio.request<dynamic>(
        opts.path,
        data: opts.data,
        queryParameters: opts.queryParameters,
        options: retryOpts,
      );
      return handler.resolve(response);
    } on AuthApiException catch (_) {
      onSessionExpired();
      return handler.next(err);
    } catch (_) {
      return handler.next(err);
    }
  }

  Future<String> _refreshOnce() {
    final existing = _completer;
    if (existing != null) return existing.future;
    final c = Completer<String>();
    _completer = c;
    onRefresh().then((token) {
      c.complete(token);
    }).catchError((Object e, StackTrace st) {
      c.completeError(e, st);
    }).whenComplete(() {
      _completer = null;
    });
    return c.future;
  }
}
