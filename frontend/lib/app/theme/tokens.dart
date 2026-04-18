// Design tokens — see frontend-spec/01-design-tokens.md.
// No widget outside lib/app/theme/ may import this file directly; everything
// flows through ThemeData + AppTheme extensions + BuildContext getters in
// theme_context.dart.
import 'package:flutter/material.dart';

/// Semantic color tokens for the light scheme.
class AppColorsLight {
  const AppColorsLight._();

  static const primary = Color(0xFF3F3D9E);
  static const onPrimary = Color(0xFFFFFFFF);
  static const primaryContainer = Color(0xFFE2E1FF);
  static const onPrimaryContainer = Color(0xFF0E0B5C);

  static const secondary = Color(0xFFB87333);
  static const onSecondary = Color(0xFFFFFFFF);
  static const secondaryContainer = Color(0xFFFBE6CC);
  static const onSecondaryContainer = Color(0xFF3A2210);

  static const tertiary = Color(0xFF2F6E5C);
  static const onTertiary = Color(0xFFFFFFFF);

  static const error = Color(0xFFB3261E);
  static const onError = Color(0xFFFFFFFF);
  static const errorContainer = Color(0xFFF9DEDC);
  static const onErrorContainer = Color(0xFF410E0B);

  static const success = Color(0xFF2E7D32);
  static const onSuccess = Color(0xFFFFFFFF);
  static const warning = Color(0xFFB26A00);
  static const onWarning = Color(0xFFFFFFFF);

  static const surface = Color(0xFFFFFBFE);
  static const onSurface = Color(0xFF1C1B1F);
  static const surfaceVariant = Color(0xFFF3EFF4);
  static const onSurfaceVariant = Color(0xFF49454F);

  static const outline = Color(0xFF79747E);
  static const outlineVariant = Color(0xFFCAC4D0);
  static const shadow = Color(0xFF000000);
  static const scrim = Color(0xFF000000);

  static const inverseSurface = Color(0xFF313033);
  static const onInverseSurface = Color(0xFFF4EFF4);
}

class AppColorsDark {
  const AppColorsDark._();

  static const primary = Color(0xFFBDBBFF);
  static const onPrimary = Color(0xFF1C1A70);
  static const primaryContainer = Color(0xFF2C2A86);
  static const onPrimaryContainer = Color(0xFFE2E1FF);

  static const secondary = Color(0xFFF1BB80);
  static const onSecondary = Color(0xFF4A2A10);
  static const secondaryContainer = Color(0xFF683F20);
  static const onSecondaryContainer = Color(0xFFFBE6CC);

  static const tertiary = Color(0xFF9BD5BF);
  static const onTertiary = Color(0xFF00382E);

  static const error = Color(0xFFF2B8B5);
  static const onError = Color(0xFF601410);
  static const errorContainer = Color(0xFF8C1D18);
  static const onErrorContainer = Color(0xFFF9DEDC);

  static const success = Color(0xFFA5D6A7);
  static const onSuccess = Color(0xFF003300);
  static const warning = Color(0xFFFFCC80);
  static const onWarning = Color(0xFF3A1F00);

  static const surface = Color(0xFF1C1B1F);
  static const onSurface = Color(0xFFE6E1E5);
  static const surfaceVariant = Color(0xFF49454F);
  static const onSurfaceVariant = Color(0xFFCAC4D0);

  static const outline = Color(0xFF938F99);
  static const outlineVariant = Color(0xFF49454F);
  static const shadow = Color(0xFF000000);
  static const scrim = Color(0xFF000000);

  static const inverseSurface = Color(0xFFE6E1E5);
  static const onInverseSurface = Color(0xFF313033);
}

/// Spacing scale (dp). Never hard-code magic numbers — always use these.
class AppSpacing {
  const AppSpacing._();
  static const double s1 = 4;
  static const double s2 = 8;
  static const double s3 = 12;
  static const double s4 = 16;
  static const double s5 = 24;
  static const double s6 = 32;
  static const double s7 = 48;
}

class AppRadius {
  const AppRadius._();
  static const double xs = 4;
  static const double sm = 8;
  static const double md = 12;
  static const double lg = 16;
  static const double pill = 999;
}

class AppElevation {
  const AppElevation._();
  static const double e0 = 0;
  static const double e1 = 1;
  static const double e2 = 2;
  static const double e4 = 4;
}

class AppMotion {
  const AppMotion._();
  static const Duration quick = Duration(milliseconds: 150);
  static const Duration standard = Duration(milliseconds: 250);
  static const Duration emphasized = Duration(milliseconds: 400);

  static const Curve quickCurve = Curves.easeOut;
  static const Curve standardCurve = Curves.easeOutCubic;
  static const Curve emphasizedCurve = Curves.easeOutExpo;

  /// Collapses durations to zero when the user has reduced-motion enabled.
  static Duration resolve(BuildContext context, Duration base) {
    final disabled = MediaQuery.maybeOf(context)?.disableAnimations ?? false;
    return disabled ? Duration.zero : base;
  }
}
