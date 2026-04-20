import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_snackbar.dart';
import '../data/settings_api.dart';

// ---------------------------------------------------------------------------
// State notifier
// ---------------------------------------------------------------------------

class _NotifPrefsNotifier
    extends AutoDisposeAsyncNotifier<NotificationPrefs> {
  @override
  Future<NotificationPrefs> build() {
    return ref.read(settingsApiProvider).getNotificationPrefs();
  }

  Future<void> toggle(String field, bool value) async {
    // Optimistic update.
    final prev = state.valueOrNull;
    if (prev == null) return;

    NotificationPrefs optimistic;
    switch (field) {
      case 'push_enabled':
        optimistic = prev.copyWith(pushEnabled: value);
        break;
      case 'email_enabled':
        optimistic = prev.copyWith(emailEnabled: value);
        break;
      case 'order_updates':
        optimistic = prev.copyWith(orderUpdates: value);
        break;
      case 'messages':
        optimistic = prev.copyWith(messages: value);
        break;
      case 'marketing':
        optimistic = prev.copyWith(marketing: value);
        break;
      default:
        return;
    }

    state = AsyncData(optimistic);

    try {
      final updated = await ref
          .read(settingsApiProvider)
          .patchNotificationPrefs({field: value});
      state = AsyncData(updated);
    } catch (_) {
      // Revert on error.
      state = AsyncData(prev);
      // Surface error via a callback captured on build; we re-set state first
      // so listeners see the revert, then the caller shows the snackbar.
      rethrow;
    }
  }
}

final _notifPrefsProvider =
    AsyncNotifierProvider.autoDispose<_NotifPrefsNotifier, NotificationPrefs>(
  _NotifPrefsNotifier.new,
);

// ---------------------------------------------------------------------------
// Screen
// ---------------------------------------------------------------------------

class NotificationPrefsScreen extends ConsumerWidget {
  const NotificationPrefsScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(_notifPrefsProvider);

    return Scaffold(
      appBar: AppTopBar(title: 'Notifications'),
      body: SafeArea(
        child: async.when(
          loading: () =>
              const Center(child: CircularProgressIndicator()),
          error: (e, _) => Center(
            child: Text(
              'Could not load preferences.',
              style: TextStyle(color: context.colors.error),
            ),
          ),
          data: (prefs) => _PrefsList(prefs: prefs),
        ),
      ),
    );
  }
}

class _PrefsList extends ConsumerWidget {
  const _PrefsList({required this.prefs});
  final NotificationPrefs prefs;

  Future<void> _toggle(
    BuildContext context,
    WidgetRef ref,
    String field,
    bool value,
  ) async {
    try {
      await ref.read(_notifPrefsProvider.notifier).toggle(field, value);
    } catch (_) {
      if (context.mounted) {
        context.showAppSnackbar(
          message: 'Could not save preference. Please try again.',
          variant: AppSnackbarVariant.error,
        );
      }
    }
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // Re-watch so SwitchListTile values stay in sync after optimistic updates.
    final p =
        ref.watch(_notifPrefsProvider).valueOrNull ?? prefs;

    return ListView(
      children: [
        SwitchListTile(
          title: const Text('Push notifications'),
          subtitle: const Text('Receive push alerts on this device'),
          value: p.pushEnabled,
          onChanged: (v) => _toggle(context, ref, 'push_enabled', v),
        ),
        SwitchListTile(
          title: const Text('Email notifications'),
          subtitle: const Text('Receive updates via email'),
          value: p.emailEnabled,
          onChanged: (v) => _toggle(context, ref, 'email_enabled', v),
        ),
        SwitchListTile(
          title: const Text('Order updates'),
          subtitle: const Text('Status changes, shipping, delivery'),
          value: p.orderUpdates,
          onChanged: (v) => _toggle(context, ref, 'order_updates', v),
        ),
        SwitchListTile(
          title: const Text('Messages'),
          subtitle: const Text('New messages from buyers or sellers'),
          value: p.messages,
          onChanged: (v) => _toggle(context, ref, 'messages', v),
        ),
        SwitchListTile(
          title: const Text('Marketing'),
          subtitle: const Text('Promotions, deals, and new arrivals'),
          value: p.marketing,
          onChanged: (v) => _toggle(context, ref, 'marketing', v),
        ),
      ],
    );
  }
}
