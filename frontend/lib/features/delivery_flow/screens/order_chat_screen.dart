import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../shared/widgets/app_app_bar.dart';
import '../../../shared/widgets/app_button.dart';
import '../state/delivery_flow_providers.dart';

/// Order-scoped chat — customer ↔ driver. Hard-deleted view on delivery
/// completion (server returns empty list for non-admins once delivered).
class OrderChatScreen extends ConsumerStatefulWidget {
  const OrderChatScreen({super.key, required this.orderId});
  final String orderId;

  @override
  ConsumerState<OrderChatScreen> createState() => _State();
}

class _State extends ConsumerState<OrderChatScreen> {
  final _ctrl = TextEditingController();
  bool _sending = false;

  Future<void> _send() async {
    if (_sending) return;
    final text = _ctrl.text.trim();
    if (text.isEmpty) return;
    setState(() => _sending = true);
    // v1: ciphertext is base64(text). Per-order HKDF AES-GCM is a Phase-12
    // follow-up tracked in POST-V1-BACKLOG.md (per-order-chat-e2e).
    final ciphertext = base64.encode(utf8.encode(text));
    const nonce = 'demo-nonce';
    try {
      await ref
          .read(deliveryFlowApiProvider)
          .postChat(widget.orderId, ciphertext, nonce);
      _ctrl.clear();
      // ignore: unused_result
      ref.refresh(orderChatProvider(widget.orderId));
    } finally {
      if (mounted) setState(() => _sending = false);
    }
  }

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(orderChatProvider(widget.orderId));
    return Scaffold(
      appBar: AppTopBar(title: 'Chat'),
      body: Column(
        children: [
          Expanded(
            child: async.when(
              loading: () => const Center(child: CircularProgressIndicator()),
              error: (_, __) => const Center(child: Text('Chat unavailable')),
              data: (msgs) {
                if (msgs.isEmpty) {
                  return const Center(
                    child: Text('No messages yet.'),
                  );
                }
                return ListView.builder(
                  padding: const EdgeInsets.all(16),
                  itemCount: msgs.length,
                  itemBuilder: (_, i) {
                    final m = msgs[i];
                    String body = '';
                    try {
                      body = utf8.decode(
                          base64.decode(m['ciphertext'] as String));
                    } catch (_) {
                      body = '[encrypted]';
                    }
                    final role = m['sender_role'] as String? ?? 'user';
                    return _MessageBubble(role: role, body: body);
                  },
                );
              },
            ),
          ),
          SafeArea(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _ctrl,
                      decoration: const InputDecoration(
                        hintText: 'Type a message…',
                        border: OutlineInputBorder(),
                      ),
                    ),
                  ),
                  const SizedBox(width: 8),
                  AppButton(
                    label: 'Send',
                    isLoading: _sending,
                    onPressed: _send,
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({required this.role, required this.body});
  final String role;
  final String body;

  @override
  Widget build(BuildContext context) {
    final isDriver = role == 'driver';
    final t = context.textStyles;
    return Align(
      alignment: isDriver ? Alignment.centerLeft : Alignment.centerRight,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 4),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        constraints: const BoxConstraints(maxWidth: 280),
        decoration: BoxDecoration(
          color: isDriver
              ? Theme.of(context).colorScheme.surfaceContainerHighest
              : const Color(0xFFB8722D),
          borderRadius: BorderRadius.circular(12),
        ),
        child: Text(body, style: t.bodyMedium),
      ),
    );
  }
}
