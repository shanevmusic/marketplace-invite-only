import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/router/routes.dart';
import '../../../app/theme/tokens.dart';
import '../../../data/api/api_client.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../data/store_dtos.dart';
import '../state/store_controller.dart';

class CreateStoreScreen extends ConsumerStatefulWidget {
  const CreateStoreScreen({super.key});

  @override
  ConsumerState<CreateStoreScreen> createState() => _CreateStoreScreenState();
}

class _CreateStoreScreenState extends ConsumerState<CreateStoreScreen> {
  final _name = TextEditingController();
  final _city = TextEditingController();
  final _desc = TextEditingController();
  bool _busy = false;

  @override
  void dispose() {
    _name.dispose();
    _city.dispose();
    _desc.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (_name.text.trim().isEmpty || _city.text.trim().isEmpty) {
      context.showAppSnackbar(message: 'Name and city are required');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(myStoreControllerProvider.notifier).create(
            CreateStoreRequest(
              name: _name.text.trim(),
              city: _city.text.trim(),
              description:
                  _desc.text.trim().isEmpty ? null : _desc.text.trim(),
            ),
          );
      final s = ref.read(myStoreControllerProvider);
      if (s.hasError) {
        if (!mounted) return;
        final e = s.error;
        final msg = e is ApiException && e.isStoreAlreadyExists
            ? 'You already have a store'
            : 'Could not create store';
        context.showAppSnackbar(message: msg);
        return;
      }
      if (!mounted) return;
      context.go(AppRoutes.sellerDashboard);
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppTopBar(title: 'Create your store'),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(AppSpacing.s4),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              AppTextField(label: 'Store name', controller: _name),
              const SizedBox(height: AppSpacing.s3),
              AppTextField(label: 'City', controller: _city),
              const SizedBox(height: AppSpacing.s3),
              AppTextField(
                label: 'Description (optional)',
                controller: _desc,
              ),
              const SizedBox(height: AppSpacing.s5),
              AppButton(
                label: 'Create store',
                isLoading: _busy,
                expand: true,
                onPressed: _busy ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
