import 'dart:async';

import 'package:flutter/material.dart';

import '../../../app/theme/theme_extensions.dart';
import '../../../app/theme/tokens.dart';

class MessageComposer extends StatefulWidget {
  const MessageComposer({
    super.key,
    required this.onSend,
    required this.onTypingChanged,
    required this.peerFirstName,
    this.enabled = true,
    this.queuedCount = 0,
  });

  final void Function(String plaintext) onSend;
  final void Function(bool typing) onTypingChanged;
  final String peerFirstName;
  final bool enabled;
  final int queuedCount;

  @override
  State<MessageComposer> createState() => _MessageComposerState();
}

class _MessageComposerState extends State<MessageComposer> {
  final _ctl = TextEditingController();
  Timer? _typingDebounce;
  bool _lastTypingEmitted = false;

  @override
  void dispose() {
    _typingDebounce?.cancel();
    _ctl.dispose();
    super.dispose();
  }

  void _onChanged(String v) {
    final typing = v.isNotEmpty;
    if (typing != _lastTypingEmitted) {
      _lastTypingEmitted = typing;
      widget.onTypingChanged(typing);
    }
    _typingDebounce?.cancel();
    if (typing) {
      _typingDebounce = Timer(const Duration(seconds: 3), () {
        widget.onTypingChanged(false);
        _lastTypingEmitted = false;
      });
    }
  }

  void _send() {
    final text = _ctl.text.trim();
    if (text.isEmpty) return;
    widget.onSend(text);
    _ctl.clear();
    widget.onTypingChanged(false);
    _lastTypingEmitted = false;
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: context.colors.surface,
        border: Border(top: BorderSide(color: context.colors.outlineVariant)),
      ),
      padding: const EdgeInsets.symmetric(
        horizontal: AppSpacing.s2,
        vertical: AppSpacing.s2,
      ),
      child: SafeArea(
        top: false,
        child: Opacity(
          opacity: widget.enabled ? 1.0 : 0.38,
          child: Row(
            children: [
              Semantics(
                button: true,
                enabled: false,
                label: 'Attach file, coming soon',
                child: IconButton(
                  icon: const Icon(Icons.attach_file),
                  tooltip: 'Attachments coming soon',
                  onPressed: null,
                ),
              ),
              Expanded(
                child: Semantics(
                  textField: true,
                  label:
                      'Message to ${widget.peerFirstName}, end-to-end encrypted',
                  child: TextField(
                    controller: _ctl,
                    enabled: widget.enabled,
                    keyboardType: TextInputType.multiline,
                    textInputAction: TextInputAction.send,
                    minLines: 1,
                    maxLines: 5,
                    onChanged: _onChanged,
                    onSubmitted: (_) => _send(),
                    decoration: InputDecoration(
                      hintText: 'Message ${widget.peerFirstName}…',
                      border: InputBorder.none,
                    ),
                  ),
                ),
              ),
              Semantics(
                button: true,
                label: 'Send',
                enabled: widget.enabled,
                child: IconButton(
                  icon: const Icon(Icons.send),
                  tooltip: 'Send',
                  onPressed: widget.enabled ? _send : null,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
