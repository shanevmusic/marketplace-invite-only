import 'package:flutter/material.dart';

import '../../app/theme/theme_extensions.dart';
import '../../app/theme/tokens.dart';

class SkeletonBox extends StatefulWidget {
  const SkeletonBox({
    super.key,
    this.width,
    required this.height,
    this.radius = AppRadius.sm,
  });

  final double? width;
  final double height;
  final double radius;

  @override
  State<SkeletonBox> createState() => _SkeletonBoxState();
}

class _SkeletonBoxState extends State<SkeletonBox>
    with SingleTickerProviderStateMixin {
  late final AnimationController _ctrl = AnimationController(
    vsync: this,
    duration: const Duration(milliseconds: 1200),
  )..repeat();

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final disabled = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    final base = context.colors.surfaceContainerHighest;
    final highlight = context.colors.surface;
    return AnimatedBuilder(
      animation: _ctrl,
      builder: (_, __) {
        final t = disabled ? 0.0 : _ctrl.value;
        final color = Color.lerp(base, highlight, (t * 2 - 1).abs())!;
        return Container(
          width: widget.width,
          height: widget.height,
          decoration: BoxDecoration(
            color: color,
            borderRadius: BorderRadius.circular(widget.radius),
          ),
        );
      },
    );
  }
}

class SkeletonLine extends StatelessWidget {
  const SkeletonLine({super.key, this.width});
  final double? width;
  @override
  Widget build(BuildContext context) =>
      SkeletonBox(width: width, height: 12, radius: AppRadius.xs);
}

class SkeletonTile extends StatelessWidget {
  const SkeletonTile({super.key});
  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s4,
          vertical: AppSpacing.s3,
        ),
        child: Row(
          // ignore: prefer_const_literals_to_create_immutables
          children: [
            const SkeletonBox(height: 40, width: 40, radius: AppRadius.pill),
            const SizedBox(width: AppSpacing.s3),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: const [
                  SkeletonLine(width: 160),
                  SizedBox(height: AppSpacing.s1),
                  SkeletonLine(width: 220),
                ],
              ),
            ),
          ],
        ),
      );
}
