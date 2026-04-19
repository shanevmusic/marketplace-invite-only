// Design tokens — see frontend-spec/01-design-tokens.md.
// No widget outside lib/app/theme/ may import this file directly; everything
// flows through ThemeData + AppTheme extensions + BuildContext getters in
// theme_context.dart.
import 'package:flutter/material.dart';

/// Semantic color tokens — dark-only burnt-amber palette (D2).
/// The `Light` class is retained as a name alias; values are the dark palette
/// so the app renders identically regardless of which factory is used.
class AppColorsLight {
  const AppColorsLight._();

  static const primary = Color(0xFFB45309);
  static const onPrimary = Color(0xFFFFF3E0);
  static const primaryContainer = Color(0xFF1F1608);
  static const onPrimaryContainer = Color(0xFFF59E0B);

  static const secondary = Color(0xFFD97706);
  static const onSecondary = Color(0xFF1A0D00);
  static const secondaryContainer = Color(0xFF2A1A08);
  static const onSecondaryContainer = Color(0xFFF59E0B);

  static const tertiary = Color(0xFF38BDF8);
  static const onTertiary = Color(0xFF001E2E);

  static const error = Color(0xFFF87171);
  static const onError = Color(0xFF1A0000);
  static const errorContainer = Color(0xFF2A0E0E);
  static const onErrorContainer = Color(0xFFFCA5A5);

  static const success = Color(0xFF4ADE80);
  static const onSuccess = Color(0xFF0F2A1E);
  static const warning = Color(0xFFF59E0B);
  static const onWarning = Color(0xFF1F1608);

  static const surface = Color(0xFF1C1C1E);
  static const onSurface = Color(0xFFF5F5F7);
  static const surfaceVariant = Color(0xFF2A2A2E);
  static const onSurfaceVariant = Color(0xFFA1A1A6);

  static const background = Color(0xFF121212);

  static const outline = Color(0xFF2A2A2E);
  static const outlineVariant = Color(0xFF3A3A3E);
  static const shadow = Color(0xFF000000);
  static const scrim = Color(0xFF000000);

  static const inverseSurface = Color(0xFFF5F5F7);
  static const onInverseSurface = Color(0xFF1C1C1E);
}

class AppColorsDark {
  const AppColorsDark._();

  static const primary = Color(0xFFB45309);
  static const onPrimary = Color(0xFFFFF3E0);
  static const primaryContainer = Color(0xFF1F1608);
  static const onPrimaryContainer = Color(0xFFF59E0B);

  static const secondary = Color(0xFFD97706);
  static const onSecondary = Color(0xFF1A0D00);
  static const secondaryContainer = Color(0xFF2A1A08);
  static const onSecondaryContainer = Color(0xFFF59E0B);

  static const tertiary = Color(0xFF38BDF8);
  static const onTertiary = Color(0xFF001E2E);

  static const error = Color(0xFFF87171);
  static const onError = Color(0xFF1A0000);
  static const errorContainer = Color(0xFF2A0E0E);
  static const onErrorContainer = Color(0xFFFCA5A5);

  static const success = Color(0xFF4ADE80);
  static const onSuccess = Color(0xFF0F2A1E);
  static const warning = Color(0xFFF59E0B);
  static const onWarning = Color(0xFF1F1608);

  static const surface = Color(0xFF1C1C1E);
  static const onSurface = Color(0xFFF5F5F7);
  static const surfaceVariant = Color(0xFF2A2A2E);
  static const onSurfaceVariant = Color(0xFFA1A1A6);

  static const background = Color(0xFF121212);

  static const outline = Color(0xFF2A2A2E);
  static const outlineVariant = Color(0xFF3A3A3E);
  static const shadow = Color(0xFF000000);
  static const scrim = Color(0xFF000000);

  static const inverseSurface = Color(0xFFF5F5F7);
  static const onInverseSurface = Color(0xFF1C1C1E);
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
