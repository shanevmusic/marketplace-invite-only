import 'package:flutter/material.dart';

import 'theme_extensions.dart';
import 'tokens.dart';

/// ThemeData factory — call [AppTheme.light] / [AppTheme.dark] from MaterialApp.
class AppTheme {
  const AppTheme._();

  static ThemeData light() => _build(
        brightness: Brightness.light,
        scheme: _lightScheme,
        semantic: AppSemanticColors.light,
        roleBadge: RoleBadgeColors.light,
      );

  static ThemeData dark() => _build(
        brightness: Brightness.dark,
        scheme: _darkScheme,
        semantic: AppSemanticColors.dark,
        roleBadge: RoleBadgeColors.dark,
      );

  static const ColorScheme _lightScheme = ColorScheme(
    brightness: Brightness.light,
    primary: AppColorsLight.primary,
    onPrimary: AppColorsLight.onPrimary,
    primaryContainer: AppColorsLight.primaryContainer,
    onPrimaryContainer: AppColorsLight.onPrimaryContainer,
    secondary: AppColorsLight.secondary,
    onSecondary: AppColorsLight.onSecondary,
    secondaryContainer: AppColorsLight.secondaryContainer,
    onSecondaryContainer: AppColorsLight.onSecondaryContainer,
    tertiary: AppColorsLight.tertiary,
    onTertiary: AppColorsLight.onTertiary,
    error: AppColorsLight.error,
    onError: AppColorsLight.onError,
    errorContainer: AppColorsLight.errorContainer,
    onErrorContainer: AppColorsLight.onErrorContainer,
    surface: AppColorsLight.surface,
    onSurface: AppColorsLight.onSurface,
    surfaceContainerHighest: AppColorsLight.surfaceVariant,
    onSurfaceVariant: AppColorsLight.onSurfaceVariant,
    outline: AppColorsLight.outline,
    outlineVariant: AppColorsLight.outlineVariant,
    shadow: AppColorsLight.shadow,
    scrim: AppColorsLight.scrim,
    inverseSurface: AppColorsLight.inverseSurface,
    onInverseSurface: AppColorsLight.onInverseSurface,
  );

  static const ColorScheme _darkScheme = ColorScheme(
    brightness: Brightness.dark,
    primary: AppColorsDark.primary,
    onPrimary: AppColorsDark.onPrimary,
    primaryContainer: AppColorsDark.primaryContainer,
    onPrimaryContainer: AppColorsDark.onPrimaryContainer,
    secondary: AppColorsDark.secondary,
    onSecondary: AppColorsDark.onSecondary,
    secondaryContainer: AppColorsDark.secondaryContainer,
    onSecondaryContainer: AppColorsDark.onSecondaryContainer,
    tertiary: AppColorsDark.tertiary,
    onTertiary: AppColorsDark.onTertiary,
    error: AppColorsDark.error,
    onError: AppColorsDark.onError,
    errorContainer: AppColorsDark.errorContainer,
    onErrorContainer: AppColorsDark.onErrorContainer,
    surface: AppColorsDark.surface,
    onSurface: AppColorsDark.onSurface,
    surfaceContainerHighest: AppColorsDark.surfaceVariant,
    onSurfaceVariant: AppColorsDark.onSurfaceVariant,
    outline: AppColorsDark.outline,
    outlineVariant: AppColorsDark.outlineVariant,
    shadow: AppColorsDark.shadow,
    scrim: AppColorsDark.scrim,
    inverseSurface: AppColorsDark.inverseSurface,
    onInverseSurface: AppColorsDark.onInverseSurface,
  );

  static TextTheme _textTheme(ColorScheme scheme) => TextTheme(
        displayLarge: TextStyle(
          fontSize: 57, fontWeight: FontWeight.w400, letterSpacing: -0.25,
          height: 64 / 57, color: scheme.onSurface,
        ),
        displayMedium: TextStyle(
          fontSize: 45, fontWeight: FontWeight.w400, letterSpacing: 0,
          height: 52 / 45, color: scheme.onSurface,
        ),
        displaySmall: TextStyle(
          fontSize: 36, fontWeight: FontWeight.w400, height: 44 / 36,
          color: scheme.onSurface,
        ),
        headlineLarge: TextStyle(
          fontSize: 32, fontWeight: FontWeight.w600, height: 40 / 32,
          color: scheme.onSurface,
        ),
        headlineMedium: TextStyle(
          fontSize: 28, fontWeight: FontWeight.w600, height: 36 / 28,
          color: scheme.onSurface,
        ),
        headlineSmall: TextStyle(
          fontSize: 24, fontWeight: FontWeight.w600, height: 32 / 24,
          color: scheme.onSurface,
        ),
        titleLarge: TextStyle(
          fontSize: 22, fontWeight: FontWeight.w600, height: 28 / 22,
          color: scheme.onSurface,
        ),
        titleMedium: TextStyle(
          fontSize: 16, fontWeight: FontWeight.w600, letterSpacing: 0.15,
          height: 24 / 16, color: scheme.onSurface,
        ),
        titleSmall: TextStyle(
          fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: 0.1,
          height: 20 / 14, color: scheme.onSurface,
        ),
        bodyLarge: TextStyle(
          fontSize: 16, fontWeight: FontWeight.w400, letterSpacing: 0.5,
          height: 24 / 16, color: scheme.onSurface,
        ),
        bodyMedium: TextStyle(
          fontSize: 14, fontWeight: FontWeight.w400, letterSpacing: 0.25,
          height: 20 / 14, color: scheme.onSurface,
        ),
        bodySmall: TextStyle(
          fontSize: 12, fontWeight: FontWeight.w400, letterSpacing: 0.4,
          height: 16 / 12, color: scheme.onSurfaceVariant,
        ),
        labelLarge: TextStyle(
          fontSize: 14, fontWeight: FontWeight.w600, letterSpacing: 0.1,
          height: 20 / 14, color: scheme.onSurface,
        ),
        labelMedium: TextStyle(
          fontSize: 12, fontWeight: FontWeight.w600, letterSpacing: 0.5,
          height: 16 / 12, color: scheme.onSurfaceVariant,
        ),
        labelSmall: TextStyle(
          fontSize: 11, fontWeight: FontWeight.w600, letterSpacing: 0.5,
          height: 16 / 11, color: scheme.onSurfaceVariant,
        ),
      );

  static ThemeData _build({
    required Brightness brightness,
    required ColorScheme scheme,
    required AppSemanticColors semantic,
    required RoleBadgeColors roleBadge,
  }) {
    final textTheme = _textTheme(scheme);
    return ThemeData(
      useMaterial3: true,
      brightness: brightness,
      colorScheme: scheme,
      scaffoldBackgroundColor: scheme.surface,
      textTheme: textTheme,
      extensions: <ThemeExtension<dynamic>>[semantic, roleBadge],
      visualDensity: VisualDensity.adaptivePlatformDensity,
      splashFactory: InkRipple.splashFactory,
      appBarTheme: AppBarTheme(
        backgroundColor: scheme.surface,
        foregroundColor: scheme.onSurface,
        elevation: AppElevation.e0,
        scrolledUnderElevation: AppElevation.e2,
        titleTextStyle: textTheme.titleLarge,
        centerTitle: false,
      ),
      inputDecorationTheme: InputDecorationTheme(
        filled: true,
        fillColor: scheme.surface,
        border: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.sm),
          borderSide: BorderSide(color: scheme.outline),
        ),
        enabledBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.sm),
          borderSide: BorderSide(color: scheme.outline),
        ),
        focusedBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.sm),
          borderSide: BorderSide(color: scheme.primary, width: 2),
        ),
        errorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.sm),
          borderSide: BorderSide(color: scheme.error, width: 2),
        ),
        focusedErrorBorder: OutlineInputBorder(
          borderRadius: BorderRadius.circular(AppRadius.sm),
          borderSide: BorderSide(color: scheme.error, width: 2),
        ),
        labelStyle: textTheme.labelMedium,
        helperStyle: textTheme.bodySmall,
        errorStyle: textTheme.bodySmall?.copyWith(color: scheme.error),
        contentPadding: const EdgeInsets.symmetric(
          horizontal: AppSpacing.s3,
          vertical: AppSpacing.s3,
        ),
      ),
      snackBarTheme: SnackBarThemeData(
        backgroundColor: scheme.inverseSurface,
        contentTextStyle:
            textTheme.bodyMedium?.copyWith(color: scheme.onInverseSurface),
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.sm),
        ),
      ),
      dialogTheme: DialogThemeData(
        backgroundColor: scheme.surface,
        elevation: AppElevation.e4,
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(AppRadius.md),
        ),
      ),
    );
  }
}
