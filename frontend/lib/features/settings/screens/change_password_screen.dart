import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../data/settings_api.dart';

class ChangePasswordScreen extends ConsumerStatefulWidget {
  const ChangePasswordScreen({super.key});

  @override
  ConsumerState<ChangePasswordScreen> createState() =>
      _ChangePasswordScreenState();
}

class _ChangePasswordScreenState extends ConsumerState<ChangePasswordScreen> {
  final _formKey = GlobalKey<FormState>();
  final _current = TextEditingController();
  final _newPw = TextEditingController();
  final _confirm = TextEditingController();

  bool _loading = false;
  // Inline error shown beneath the Current password field on 400 response.
  String? _currentPwError;

  @override
  void dispose() {
    _current.dispose();
    _newPw.dispose();
    _confirm.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    // Clear previous server-side error before revalidating.
    setState(() => _currentPwError = null);
    if (!(_formKey.currentState?.validate() ?? false)) return;

    setState(() => _loading = true);
    try {
      await ref.read(settingsApiProvider).changePassword(
            ChangePasswordRequest(
              currentPassword: _current.text,
              newPassword: _newPw.text,
            ),
          );
      if (!mounted) return;
      context.showAppSnackbar(
        message: 'Password updated.',
        variant: AppSnackbarVariant.success,
      );
      Navigator.of(context).pop();
    } catch (e) {
      if (!mounted) return;
      // 400 with detail = "Current password is incorrect"
      final isWrongPw = e.toString().toLowerCase().contains('current password');
      if (isWrongPw) {
        setState(() => _currentPwError = 'Current password is incorrect.');
        // Re-run form validation so the error shows immediately.
        _formKey.currentState?.validate();
      } else {
        context.showAppSnackbar(
          message: 'Failed to update password. Please try again.',
          variant: AppSnackbarVariant.error,
        );
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppTopBar(title: 'Change password'),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.s4),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: AppSpacing.s2),
                // Current password — shows server error when _currentPwError set.
                AppTextField(
                  controller: _current,
                  label: 'Current password',
                  kind: AppTextFieldKind.password,
                  textInputAction: TextInputAction.next,
                  errorText: _currentPwError,
                ),
                const SizedBox(height: AppSpacing.s4),
                // New password with client-side length validation.
                _ValidatedPasswordField(
                  controller: _newPw,
                  label: 'New password',
                  validator: (v) {
                    if (v == null || v.isEmpty) return 'Required.';
                    if (v.length < 8) {
                      return 'Password must be at least 8 characters.';
                    }
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.s4),
                // Confirm new password.
                _ValidatedPasswordField(
                  controller: _confirm,
                  label: 'Confirm new password',
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _submit(),
                  validator: (v) {
                    if (v == null || v.isEmpty) return 'Required.';
                    if (v != _newPw.text) return 'Passwords do not match.';
                    return null;
                  },
                ),
                const SizedBox(height: AppSpacing.s6),
                AppButton(
                  label: 'Update password',
                  expand: true,
                  size: AppButtonSize.lg,
                  isLoading: _loading,
                  onPressed: _loading ? null : _submit,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

/// Thin wrapper that attaches a [FormField] validator around [AppTextField].
/// AppTextField itself doesn't integrate with Form; this widget bridges that.
class _ValidatedPasswordField extends StatefulWidget {
  const _ValidatedPasswordField({
    required this.controller,
    required this.label,
    required this.validator,
    this.textInputAction,
    this.onSubmitted,
  });

  final TextEditingController controller;
  final String label;
  final String? Function(String?) validator;
  final TextInputAction? textInputAction;
  final ValueChanged<String>? onSubmitted;

  @override
  State<_ValidatedPasswordField> createState() =>
      _ValidatedPasswordFieldState();
}

class _ValidatedPasswordFieldState extends State<_ValidatedPasswordField> {
  String? _errorText;

  @override
  Widget build(BuildContext context) {
    // Use FormField for validator integration.
    return FormField<String>(
      validator: (v) {
        final err = widget.validator(widget.controller.text);
        setState(() => _errorText = err);
        return err;
      },
      builder: (_) => AppTextField(
        controller: widget.controller,
        label: widget.label,
        kind: AppTextFieldKind.password,
        textInputAction: widget.textInputAction ?? TextInputAction.next,
        errorText: _errorText,
        onSubmitted: widget.onSubmitted,
        onChanged: (_) {
          // Clear inline error as user types so it doesn't linger.
          if (_errorText != null) setState(() => _errorText = null);
        },
      ),
    );
  }
}
