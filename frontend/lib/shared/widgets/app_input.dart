import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../app/theme/tokens.dart';

enum AppTextFieldKind { text, email, password, numeric }

class AppTextField extends StatefulWidget {
  const AppTextField({
    super.key,
    required this.controller,
    required this.label,
    this.kind = AppTextFieldKind.text,
    this.hint,
    this.helperText,
    this.errorText,
    this.leadingIcon,
    this.trailingIcon,
    this.textInputAction,
    this.autofillHints,
    this.onChanged,
    this.onSubmitted,
    this.enabled = true,
    this.semanticsLabel,
  });

  final TextEditingController controller;
  final String label;
  final AppTextFieldKind kind;
  final String? hint;
  final String? helperText;
  final String? errorText;
  final IconData? leadingIcon;
  final Widget? trailingIcon;
  final TextInputAction? textInputAction;
  final List<String>? autofillHints;
  final ValueChanged<String>? onChanged;
  final ValueChanged<String>? onSubmitted;
  final bool enabled;
  final String? semanticsLabel;

  @override
  State<AppTextField> createState() => _AppTextFieldState();
}

class _AppTextFieldState extends State<AppTextField> {
  late bool _obscure;

  @override
  void initState() {
    super.initState();
    _obscure = widget.kind == AppTextFieldKind.password;
  }

  TextInputType get _keyboardType {
    switch (widget.kind) {
      case AppTextFieldKind.email:
        return TextInputType.emailAddress;
      case AppTextFieldKind.password:
        return TextInputType.visiblePassword;
      case AppTextFieldKind.numeric:
        return TextInputType.number;
      case AppTextFieldKind.text:
        return TextInputType.text;
    }
  }

  @override
  Widget build(BuildContext context) {
    final suffix = widget.kind == AppTextFieldKind.password
        ? IconButton(
            icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility),
            tooltip: _obscure ? 'Show password' : 'Hide password',
            onPressed: () => setState(() => _obscure = !_obscure),
          )
        : widget.trailingIcon;

    return Semantics(
      textField: true,
      label: widget.semanticsLabel ?? widget.label,
      child: TextField(
        controller: widget.controller,
        obscureText: _obscure,
        enabled: widget.enabled,
        keyboardType: _keyboardType,
        textInputAction: widget.textInputAction,
        autofillHints: widget.autofillHints,
        autocorrect: widget.kind != AppTextFieldKind.email &&
            widget.kind != AppTextFieldKind.password,
        enableSuggestions: widget.kind == AppTextFieldKind.text,
        inputFormatters: widget.kind == AppTextFieldKind.numeric
            ? [FilteringTextInputFormatter.digitsOnly]
            : null,
        onChanged: widget.onChanged,
        onSubmitted: widget.onSubmitted,
        decoration: InputDecoration(
          labelText: widget.label,
          hintText: widget.hint,
          helperText: widget.errorText == null ? widget.helperText : null,
          errorText: widget.errorText,
          prefixIcon:
              widget.leadingIcon != null ? Icon(widget.leadingIcon) : null,
          suffixIcon: suffix,
          contentPadding: const EdgeInsets.symmetric(
            horizontal: AppSpacing.s3,
            vertical: AppSpacing.s3,
          ),
        ),
      ),
    );
  }
}
