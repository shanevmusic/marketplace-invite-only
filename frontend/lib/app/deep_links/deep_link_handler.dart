import 'dart:async';

import 'package:app_links/app_links.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../features/auth/state/auth_controller.dart';
import '../../shared/widgets/app_dialog.dart';
import '../router/app_router.dart';
import '../router/routes.dart';

/// Initializes deep-link listening after the router is built. Handles both
/// the cold-start URI and warm links via the app_links stream.
///
/// On invite-shaped links:
///   * unauth: routes to /invite/:token (InviteLandingScreen validates).
///   * authed: prompts with a "switch account" dialog (spec §4).
class DeepLinkHandler {
  DeepLinkHandler(this._ref);
  final Ref _ref;
  StreamSubscription<Uri>? _sub;
  final _appLinks = AppLinks();

  Future<void> init(BuildContext context) async {
    try {
      final initial = await _appLinks.getInitialLink();
      if (initial != null) _handle(context, initial);
    } catch (_) {}
    _sub = _appLinks.uriLinkStream.listen((uri) => _handle(context, uri));
  }

  void dispose() => _sub?.cancel();

  void _handle(BuildContext context, Uri uri) {
    final token = _extractInviteToken(uri);
    if (token == null) return;

    final router = _ref.read(goRouterProvider);
    final session = _ref.read(authControllerProvider).valueOrNull;

    if (session == null) {
      router.go(AppRoutes.invite(token));
      return;
    }

    // Authed — confirm before tearing down session.
    AppDialog.show(
      context,
      title: 'Use this invite?',
      body: Text(
        "You're signed in as ${session.user.email} "
        "(${session.user.role}). This invite is for a new account.",
      ),
      primaryAction: AppDialogAction(
        label: 'Use this invite',
        onPressed: () async {
          Navigator.of(context).pop();
          await _ref.read(authControllerProvider.notifier).logout();
          router.go(AppRoutes.invite(token));
        },
      ),
      secondaryAction: AppDialogAction(
        label: 'Stay signed in',
        onPressed: () => Navigator.of(context).pop(),
      ),
    );
  }

  String? _extractInviteToken(Uri uri) {
    // marketplace://invite/<token>  or  https://<domain>/invite/<token>
    if (uri.scheme == 'marketplace' && uri.host == 'invite') {
      final seg = uri.pathSegments;
      return seg.isNotEmpty ? seg.first : null;
    }
    if ((uri.scheme == 'https' || uri.scheme == 'http') &&
        uri.pathSegments.length >= 2 &&
        uri.pathSegments[0] == 'invite') {
      return uri.pathSegments[1];
    }
    return null;
  }
}

final deepLinkHandlerProvider =
    Provider<DeepLinkHandler>((ref) => DeepLinkHandler(ref));
