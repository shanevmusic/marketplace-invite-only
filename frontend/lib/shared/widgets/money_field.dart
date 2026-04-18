import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../format/money.dart';

/// Form field for monetary amounts. Yields `int minorUnits` via [onChanged].
/// Display preview uses [formatMoney]; internal digit-only TextField keeps
/// input simple and locale-independent.
class MoneyField extends StatefulWidget {
  const MoneyField({
    super.key,
    this.initialMinor,
    this.currencyCode = 'USD',
    required this.onChanged,
    this.errorText,
    this.label,
  });

  final int? initialMinor;
  final String currencyCode;
  final ValueChanged<int?> onChanged;
  final String? errorText;
  final String? label;

  @override
  State<MoneyField> createState() => _MoneyFieldState();
}

class _MoneyFieldState extends State<MoneyField> {
  late final TextEditingController _controller;

  @override
  void initState() {
    super.initState();
    _controller = TextEditingController(
      text: widget.initialMinor != null ? '${widget.initialMinor}' : '',
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final raw = _controller.text.trim();
    final minor = raw.isEmpty ? null : int.tryParse(raw);
    final preview = minor == null
        ? ''
        : formatMoney(minor, currencyCode: widget.currencyCode);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Semantics(
          textField: true,
          label: widget.label ?? 'Price',
          child: TextField(
            controller: _controller,
            keyboardType: TextInputType.number,
            inputFormatters: [FilteringTextInputFormatter.digitsOnly],
            decoration: InputDecoration(
              labelText: widget.label,
              helperText: preview.isNotEmpty ? preview : null,
              errorText: widget.errorText,
              hintText: 'minor units (e.g. 1299 = \$12.99)',
            ),
            onChanged: (v) {
              final n = v.trim().isEmpty ? null : int.tryParse(v.trim());
              widget.onChanged(n);
              setState(() {});
            },
          ),
        ),
      ],
    );
  }
}
