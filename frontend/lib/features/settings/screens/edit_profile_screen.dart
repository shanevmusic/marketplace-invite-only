import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../../auth/state/auth_controller.dart';
import '../data/settings_api.dart';

class EditProfileScreen extends ConsumerStatefulWidget {
  const EditProfileScreen({super.key});

  @override
  ConsumerState<EditProfileScreen> createState() => _EditProfileScreenState();
}

class _EditProfileScreenState extends ConsumerState<EditProfileScreen> {
  final _formKey = GlobalKey<FormState>();
  late final TextEditingController _displayName;
  late final TextEditingController _phone;
  late final TextEditingController _avatarUrl;

  bool _loading = false;

  @override
  void initState() {
    super.initState();
    final session = ref.read(authControllerProvider).valueOrNull;
    _displayName =
        TextEditingController(text: session?.user.displayName ?? '');
    // AuthUser doesn't carry phone/avatarUrl — pre-populate empty.
    _phone = TextEditingController();
    _avatarUrl = TextEditingController();
  }

  @override
  void dispose() {
    _displayName.dispose();
    _phone.dispose();
    _avatarUrl.dispose();
    super.dispose();
  }

  Future<void> _save() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    setState(() => _loading = true);
    try {
      await ref.read(settingsApiProvider).patchMe(
            PatchMeRequest(
              displayName: _displayName.text.trim().isEmpty
                  ? null
                  : _displayName.text.trim(),
              phone:
                  _phone.text.trim().isEmpty ? null : _phone.text.trim(),
              avatarUrl: _avatarUrl.text.trim().isEmpty
                  ? null
                  : _avatarUrl.text.trim(),
            ),
          );
      if (!mounted) return;
      context.showAppSnackbar(
        message: 'Profile updated.',
        variant: AppSnackbarVariant.success,
      );
      Navigator.of(context).pop();
    } catch (_) {
      if (!mounted) return;
      context.showAppSnackbar(
        message: 'Failed to update profile. Please try again.',
        variant: AppSnackbarVariant.error,
      );
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppTopBar(title: 'Edit profile'),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(AppSpacing.s4),
          child: Form(
            key: _formKey,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                const SizedBox(height: AppSpacing.s2),
                AppTextField(
                  controller: _displayName,
                  label: 'Display name',
                  kind: AppTextFieldKind.text,
                  textInputAction: TextInputAction.next,
                ),
                const SizedBox(height: AppSpacing.s4),
                AppTextField(
                  controller: _phone,
                  label: 'Phone',
                  kind: AppTextFieldKind.numeric,
                  textInputAction: TextInputAction.next,
                ),
                const SizedBox(height: AppSpacing.s4),
                AppTextField(
                  controller: _avatarUrl,
                  label: 'Avatar URL',
                  kind: AppTextFieldKind.text,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _save(),
                ),
                const SizedBox(height: AppSpacing.s6),
                AppButton(
                  label: 'Save',
                  expand: true,
                  size: AppButtonSize.lg,
                  isLoading: _loading,
                  onPressed: _loading ? null : _save,
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
