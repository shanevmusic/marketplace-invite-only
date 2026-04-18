import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_empty_state.dart';
import '../data/auth_dtos.dart';
import '../state/auth_controller.dart';
import 'signup_screen.dart';

class InviteLandingScreen extends ConsumerStatefulWidget {
  const InviteLandingScreen({super.key, required this.token});
  final String token;

  @override
  ConsumerState<InviteLandingScreen> createState() =>
      _InviteLandingScreenState();
}

class _InviteLandingScreenState extends ConsumerState<InviteLandingScreen> {
  InviteValidation? _validation;
  AuthApiException? _error;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    _validate();
  }

  Future<void> _validate() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final repo = ref.read(authRepositoryProvider);
      final v = await repo.validateInvite(widget.token);
      setState(() {
        _validation = v;
        _loading = false;
      });
    } on AuthApiException catch (e) {
      setState(() {
        _error = e;
        _loading = false;
      });
    }
  }

  String get _maskedToken {
    if (widget.token.length <= 6) return widget.token;
    return '${widget.token.substring(0, 4)}…';
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(child: _body(context)),
    );
  }

  Widget _body(BuildContext context) {
    if (_loading) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: AppSpacing.s4),
            Text('Verifying invite $_maskedToken',
                style: context.textStyles.bodyMedium),
          ],
        ),
      );
    }
    final err = _error;
    if (err != null) {
      final (headline, subhead) = _errorCopy(err);
      return AppEmptyState(
        icon: Icons.lock_outline,
        headline: headline,
        subhead: subhead,
        ctaLabel: err.isNetwork ? 'Retry' : 'Close',
        onCtaPressed:
            err.isNetwork ? _validate : () => context.go(AppRoutes.login),
      );
    }

    final v = _validation!;
    final inviter = v.inviterName ?? 'Someone you trust';
    final roleLine = v.role == 'seller'
        ? 'to join as a seller'
        : v.role == 'customer'
            ? 'to join as a customer'
            : 'to connect with their store';
    return Padding(
      padding: const EdgeInsets.all(AppSpacing.s5),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const SizedBox(height: AppSpacing.s7),
          Text("You've been invited by $inviter",
              style: context.textStyles.headlineMedium),
          const SizedBox(height: AppSpacing.s2),
          Text(roleLine, style: context.textStyles.bodyLarge),
          const Spacer(),
          AppButton(
            label: 'Continue',
            size: AppButtonSize.lg,
            expand: true,
            onPressed: () {
              context.go(
                '${AppRoutes.signup}?invite_token=${widget.token}',
                extra: SignupScreenArgs(
                  inviteToken: widget.token,
                  roleChoiceRequired: v.roleChoiceRequired,
                  inviterName: v.inviterName,
                ),
              );
            },
          ),
          const SizedBox(height: AppSpacing.s4),
        ],
      ),
    );
  }

  (String, String) _errorCopy(AuthApiException e) {
    switch (e.code) {
      case 'INVITE_NOT_FOUND':
        return (
          'Invite not recognized',
          "This link isn't valid. Ask for a new invite."
        );
      case 'INVITE_EXPIRED':
        return (
          'Invite expired',
          'Invites expire for security. Ask for a fresh link.'
        );
      case 'INVITE_ALREADY_USED':
        return (
          'Invite already used',
          "This invite has already been claimed. If that wasn't you, "
              'contact an admin.'
        );
      case 'NETWORK':
        return ("Can't verify invite", 'Check your connection and try again.');
      default:
        return (
          'Invite unavailable',
          e.message ?? 'Try again or ask for a new invite.'
        );
    }
  }
}
