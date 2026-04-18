import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

class QuantityStepper extends StatelessWidget {
  const QuantityStepper({
    super.key,
    required this.value,
    required this.onChanged,
    this.min = 1,
    this.max = 99,
    this.enabled = true,
    this.semanticsLabelPrefix,
  });

  final int value;
  final int min;
  final int max;
  final ValueChanged<int> onChanged;
  final bool enabled;
  final String? semanticsLabelPrefix;

  @override
  Widget build(BuildContext context) {
    final canDec = enabled && value > min;
    final canInc = enabled && value < max;
    final prefix = semanticsLabelPrefix ?? 'quantity';
    return Container(
      height: 40,
      decoration: BoxDecoration(
        color: context.colors.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(AppRadius.pill),
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _StepperButton(
            icon: Icons.remove,
            enabled: canDec,
            onTap: canDec ? () => onChanged(value - 1) : null,
            semanticsLabel: 'Decrease $prefix, current $value',
          ),
          SizedBox(
            width: 40,
            child: Semantics(
              liveRegion: true,
              label: 'Quantity $value',
              child: Text(
                '$value',
                textAlign: TextAlign.center,
                style: context.textStyles.titleMedium,
              ),
            ),
          ),
          _StepperButton(
            icon: Icons.add,
            enabled: canInc,
            onTap: canInc ? () => onChanged(value + 1) : null,
            semanticsLabel: 'Increase $prefix, current $value',
          ),
        ],
      ),
    );
  }
}

class _StepperButton extends StatelessWidget {
  const _StepperButton({
    required this.icon,
    required this.enabled,
    required this.onTap,
    required this.semanticsLabel,
  });

  final IconData icon;
  final bool enabled;
  final VoidCallback? onTap;
  final String semanticsLabel;

  @override
  Widget build(BuildContext context) {
    final color =
        context.colors.onSurfaceVariant.withValues(alpha: enabled ? 1.0 : 0.38);
    return Semantics(
      button: true,
      enabled: enabled,
      label: semanticsLabel,
      child: InkWell(
        onTap: onTap,
        customBorder: const CircleBorder(),
        child: SizedBox(
          width: 44,
          height: 44,
          child: Icon(icon, size: 20, color: color),
        ),
      ),
    );
  }
}
