import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../../../shared/widgets/form_field_wrapper.dart';
import '../data/auth_dtos.dart';
import '../state/auth_controller.dart';

final _emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

class LoginScreen extends ConsumerStatefulWidget {
  const LoginScreen({super.key});

  @override
  ConsumerState<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends ConsumerState<LoginScreen> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  String? _formError;
  bool _submitted = false;

  @override
  void initState() {
    super.initState();
    _email.addListener(() => setState(() {}));
    _password.addListener(() => setState(() {}));
  }

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    super.dispose();
  }

  bool get _valid =>
      _emailRegex.hasMatch(_email.text.trim()) &&
      _password.text.length >= 1;

  Future<void> _submit() async {
    if (!_valid) return;
    setState(() {
      _formError = null;
      _submitted = true;
    });
    try {
      await ref.read(authControllerProvider.notifier).login(
            email: _email.text.trim(),
            password: _password.text,
          );
    } on Object {
      // error is surfaced via the AsyncValue below
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authControllerProvider);

    // Surface expired-session toast once per arrival.
    ref.listen<bool>(sessionExpiredFlagProvider, (prev, next) {
      if (next) {
        context.showAppSnackbar(
          message: 'Your session expired. Please sign in again.',
          variant: AppSnackbarVariant.info,
        );
        ref.read(sessionExpiredFlagProvider.notifier).state = false;
      }
    });

    final err = state.error;
    String? emailError;
    String? passwordError;
    String? banner;
    if (err is AuthApiException && _submitted) {
      if (err.isInvalidCredentials) {
        passwordError = 'Incorrect email or password.';
      } else if (err.isRateLimited) {
        banner = 'Too many attempts. Try again in a minute.';
      } else if (err.isNetwork) {
        banner = "Can't reach the server. Check your connection.";
      } else if (err.code == 'VALIDATION_ERROR') {
        banner = err.message ?? 'Please check your inputs and try again.';
      } else {
        banner = err.message ?? 'Sign-in failed.';
      }
    }

    return Scaffold(
      body: SafeArea(
        child: Center(
          child: SingleChildScrollView(
            padding: const EdgeInsets.all(AppSpacing.s4),
            child: AutofillGroup(
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const SizedBox(height: AppSpacing.s7),
                    Text('Welcome back',
                        style: context.textStyles.headlineLarge),
                    const SizedBox(height: AppSpacing.s2),
                    Text(
                      'Sign in to continue.',
                      style: context.textStyles.bodyMedium?.copyWith(
                        color: context.colors.onSurfaceVariant,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.s6),
                    if (banner != null) ...[
                      Container(
                        padding: const EdgeInsets.all(AppSpacing.s3),
                        decoration: BoxDecoration(
                          color: context.colors.errorContainer,
                          borderRadius: BorderRadius.circular(AppRadius.sm),
                        ),
                        child: Text(
                          banner,
                          style: context.textStyles.bodyMedium?.copyWith(
                            color: context.colors.onErrorContainer,
                          ),
                        ),
                      ),
                      const SizedBox(height: AppSpacing.s4),
                    ],
                    AppFormField(
                      label: 'Email',
                      errorText: emailError,
                      child: AppTextField(
                        controller: _email,
                        label: 'Email',
                        kind: AppTextFieldKind.email,
                        autofillHints: const [AutofillHints.email],
                        textInputAction: TextInputAction.next,
                      ),
                    ),
                    const SizedBox(height: AppSpacing.s4),
                    AppFormField(
                      label: 'Password',
                      errorText: passwordError,
                      child: AppTextField(
                        controller: _password,
                        label: 'Password',
                        kind: AppTextFieldKind.password,
                        autofillHints: const [AutofillHints.password],
                        textInputAction: TextInputAction.done,
                        onSubmitted: (_) => _submit(),
                      ),
                    ),
                    const SizedBox(height: AppSpacing.s5),
                    AppButton(
                      label: 'Sign in',
                      expand: true,
                      size: AppButtonSize.lg,
                      isLoading: state.isLoading,
                      onPressed: _valid ? _submit : null,
                    ),
                    const SizedBox(height: AppSpacing.s4),
                    Text(
                      'Have an invite? Open the invite link to create your '
                      'account.',
                      style: context.textStyles.bodySmall,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
