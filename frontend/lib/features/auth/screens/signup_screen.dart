import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_card.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/form_field_wrapper.dart';
import '../data/auth_dtos.dart';
import '../state/auth_controller.dart';

final _emailRegex = RegExp(r'^[^@\s]+@[^@\s]+\.[^@\s]+$');

class SignupScreenArgs {
  const SignupScreenArgs({
    required this.inviteToken,
    this.roleChoiceRequired = false,
    this.inviterName,
  });
  final String inviteToken;
  final bool roleChoiceRequired;
  final String? inviterName;
}

class SignupScreen extends ConsumerStatefulWidget {
  const SignupScreen({super.key, required this.args});
  final SignupScreenArgs args;

  @override
  ConsumerState<SignupScreen> createState() => _SignupScreenState();
}

class _SignupScreenState extends ConsumerState<SignupScreen> {
  final _name = TextEditingController();
  final _email = TextEditingController();
  final _phone = TextEditingController();
  final _password = TextEditingController();
  String _roleChoice = 'customer';
  bool _submitted = false;
  String? _emailFieldError;

  @override
  void initState() {
    super.initState();
    for (final c in [_name, _email, _phone, _password]) {
      c.addListener(() => setState(() {}));
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _email.dispose();
    _phone.dispose();
    _password.dispose();
    super.dispose();
  }

  bool get _valid =>
      _name.text.trim().length >= 2 &&
      _emailRegex.hasMatch(_email.text.trim()) &&
      _password.text.length >= 12;

  Future<void> _submit() async {
    if (!_valid) return;
    setState(() {
      _submitted = true;
      _emailFieldError = null;
    });
    final body = SignupRequest(
      inviteToken: widget.args.inviteToken,
      displayName: _name.text.trim(),
      email: _email.text.trim(),
      password: _password.text,
      phone: _phone.text.trim().isEmpty ? null : _phone.text.trim(),
      roleChoice: widget.args.roleChoiceRequired ? _roleChoice : null,
    );
    try {
      await ref.read(authControllerProvider.notifier).signup(body);
    } on Object {
      // surfaced via AsyncValue
    }
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(authControllerProvider);
    final err = state.error;
    String? banner;
    if (err is AuthApiException && _submitted) {
      if (err.isEmailTaken) {
        _emailFieldError = 'An account with this email already exists.';
      } else if (err.code == 'INVITE_ALREADY_USED' ||
          err.code == 'INVITE_EXPIRED' ||
          err.code == 'INVITE_NOT_FOUND') {
        banner = err.message ?? 'This invite is no longer valid.';
      } else if (err.isNetwork) {
        banner = "Can't reach the server. Check your connection.";
      } else if (err.code == 'VALIDATION_ERROR') {
        banner = err.message ?? 'Please fix the highlighted fields.';
      }
    }

    return Scaffold(
      appBar: AppBar(title: const Text('Create account')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.s4),
          child: AutofillGroup(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 420),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (widget.args.inviterName != null)
                    Padding(
                      padding: const EdgeInsets.only(bottom: AppSpacing.s5),
                      child: Text(
                        "You've been invited by "
                        "${widget.args.inviterName}",
                        style: context.textStyles.titleMedium,
                      ),
                    ),
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
                    label: 'Display name',
                    required: true,
                    child: AppTextField(
                      controller: _name,
                      label: 'Display name',
                      autofillHints: const [AutofillHints.name],
                      textInputAction: TextInputAction.next,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.s4),
                  AppFormField(
                    label: 'Email',
                    required: true,
                    errorText: _emailFieldError,
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
                    label: 'Phone (optional)',
                    child: AppTextField(
                      controller: _phone,
                      label: 'Phone',
                      kind: AppTextFieldKind.numeric,
                      autofillHints: const [AutofillHints.telephoneNumber],
                      textInputAction: TextInputAction.next,
                    ),
                  ),
                  const SizedBox(height: AppSpacing.s4),
                  AppFormField(
                    label: 'Password',
                    required: true,
                    helperText: 'Minimum 12 characters.',
                    child: AppTextField(
                      controller: _password,
                      label: 'Password',
                      kind: AppTextFieldKind.password,
                      autofillHints: const [AutofillHints.newPassword],
                      textInputAction: TextInputAction.done,
                      onSubmitted: (_) => _submit(),
                    ),
                  ),
                  if (widget.args.roleChoiceRequired) ...[
                    const SizedBox(height: AppSpacing.s5),
                    Text(
                      'Which kind of account do you want?',
                      style: context.textStyles.titleMedium,
                    ),
                    const SizedBox(height: AppSpacing.s2),
                    _RoleChoiceCard(
                      label: 'Customer',
                      description:
                          "Browse and order from "
                          "${widget.args.inviterName ?? 'their'} store",
                      selected: _roleChoice == 'customer',
                      onTap: () => setState(() => _roleChoice = 'customer'),
                    ),
                    const SizedBox(height: AppSpacing.s2),
                    _RoleChoiceCard(
                      label: 'Seller',
                      description:
                          'Run your own store, invited by '
                          '${widget.args.inviterName ?? 'them'}',
                      selected: _roleChoice == 'seller',
                      onTap: () => setState(() => _roleChoice = 'seller'),
                    ),
                  ],
                  const SizedBox(height: AppSpacing.s5),
                  AppButton(
                    label: 'Create account',
                    size: AppButtonSize.lg,
                    expand: true,
                    isLoading: state.isLoading,
                    onPressed: _valid ? _submit : null,
                  ),
                  const SizedBox(height: AppSpacing.s3),
                  Text(
                    'By creating an account you agree to the Terms & Privacy.',
                    style: context.textStyles.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _RoleChoiceCard extends StatelessWidget {
  const _RoleChoiceCard({
    required this.label,
    required this.description,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final String description;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return AppCard(
      variant: selected ? AppCardVariant.selected : AppCardVariant.interactive,
      onTap: onTap,
      child: Row(
        children: [
          Radio<bool>(
            value: true,
            groupValue: selected,
            onChanged: (_) => onTap(),
          ),
          const SizedBox(width: AppSpacing.s2),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(label, style: context.textStyles.titleMedium),
                const SizedBox(height: AppSpacing.s1),
                Text(
                  description,
                  style: context.textStyles.bodyMedium?.copyWith(
                    color: context.colors.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
