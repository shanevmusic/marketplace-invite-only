import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../app/theme/tokens.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../../../shared/widgets/app_input.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../data/store_dtos.dart';
import '../state/store_controller.dart';

/// Lets the seller edit their existing store: name, city, description,
/// and toggle public/invite-only visibility.
class EditStoreScreen extends ConsumerStatefulWidget {
  const EditStoreScreen({super.key});

  @override
  ConsumerState<EditStoreScreen> createState() => _EditStoreScreenState();
}

class _EditStoreScreenState extends ConsumerState<EditStoreScreen> {
  final _name = TextEditingController();
  final _city = TextEditingController();
  final _desc = TextEditingController();
  bool _busy = false;
  bool _isPublic = false;
  bool _isActive = true;
  bool _initialised = false;

  @override
  void dispose() {
    _name.dispose();
    _city.dispose();
    _desc.dispose();
    super.dispose();
  }

  void _hydrate(StoreResponse store) {
    if (_initialised) return;
    _name.text = store.name;
    _city.text = store.city;
    _desc.text = store.description;
    _isPublic = store.isPublic;
    _isActive = store.isActive;
    _initialised = true;
  }

  Future<void> _submit() async {
    if (_name.text.trim().isEmpty || _city.text.trim().isEmpty) {
      context.showAppSnackbar(message: 'Name and city are required');
      return;
    }
    setState(() => _busy = true);
    try {
      await ref.read(myStoreControllerProvider.notifier).updateStore(
            UpdateStoreRequest(
              name: _name.text.trim(),
              city: _city.text.trim(),
              description: _desc.text.trim(),
              isActive: _isActive,
              isPublic: _isPublic,
            ),
          );
      final s = ref.read(myStoreControllerProvider);
      if (s.hasError) {
        if (!mounted) return;
        context.showAppSnackbar(message: 'Could not update store');
        return;
      }
      if (!mounted) return;
      context.showAppSnackbar(message: 'Store updated');
      context.pop();
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final storeAsync = ref.watch(myStoreControllerProvider);
    return Scaffold(
      appBar: AppTopBar(title: 'Edit store'),
      body: SafeArea(
        child: storeAsync.when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (_, __) => const Center(child: Text('Could not load store')),
          data: (store) {
            if (store == null) {
              return const Center(child: Text('Create a store first'));
            }
            _hydrate(store);
            return Padding(
              padding: const EdgeInsets.all(AppSpacing.s4),
              child: ListView(
                children: [
                  AppTextField(label: 'Store name', controller: _name),
                  const SizedBox(height: AppSpacing.s3),
                  AppTextField(label: 'City', controller: _city),
                  const SizedBox(height: AppSpacing.s3),
                  AppTextField(
                    label: 'Description',
                    controller: _desc,
                  ),
                  const SizedBox(height: AppSpacing.s4),
                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    value: _isPublic,
                    onChanged:
                        _busy ? null : (v) => setState(() => _isPublic = v),
                    title: const Text('Public store'),
                    subtitle: const Text(
                      'Anyone signed up to the app can find your store. Off by default — only customers you invite can see your store.',
                    ),
                  ),
                  SwitchListTile.adaptive(
                    contentPadding: EdgeInsets.zero,
                    value: _isActive,
                    onChanged:
                        _busy ? null : (v) => setState(() => _isActive = v),
                    title: const Text('Store is active'),
                    subtitle: const Text(
                      'When off, your store and products are hidden from customers.',
                    ),
                  ),
                  const SizedBox(height: AppSpacing.s5),
                  AppButton(
                    label: 'Save changes',
                    isLoading: _busy,
                    expand: true,
                    onPressed: _busy ? null : _submit,
                  ),
                ],
              ),
            );
          },
        ),
      ),
    );
  }
}
