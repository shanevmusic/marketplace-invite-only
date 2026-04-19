import 'package:flutter/material.dart';

import 'tokens.dart';

/// Non-M3 semantic colors: success, warning. Exposed via ThemeExtension so
/// widgets read them through Theme.of(context).extension<AppSemanticColors>().
@immutable
class AppSemanticColors extends ThemeExtension<AppSemanticColors> {
  const AppSemanticColors({
    required this.success,
    required this.onSuccess,
    required this.warning,
    required this.onWarning,
  });

  final Color success;
  final Color onSuccess;
  final Color warning;
  final Color onWarning;

  static const light = AppSemanticColors(
    success: AppColorsLight.success,
    onSuccess: AppColorsLight.onSuccess,
    warning: AppColorsLight.warning,
    onWarning: AppColorsLight.onWarning,
  );

  static const dark = AppSemanticColors(
    success: AppColorsDark.success,
    onSuccess: AppColorsDark.onSuccess,
    warning: AppColorsDark.warning,
    onWarning: AppColorsDark.onWarning,
  );

  @override
  AppSemanticColors copyWith({
    Color? success,
    Color? onSuccess,
    Color? warning,
    Color? onWarning,
  }) =>
      AppSemanticColors(
        success: success ?? this.success,
        onSuccess: onSuccess ?? this.onSuccess,
        warning: warning ?? this.warning,
        onWarning: onWarning ?? this.onWarning,
      );

  @override
  AppSemanticColors lerp(ThemeExtension<AppSemanticColors>? other, double t) {
    if (other is! AppSemanticColors) return this;
    return AppSemanticColors(
      success: Color.lerp(success, other.success, t)!,
      onSuccess: Color.lerp(onSuccess, other.onSuccess, t)!,
      warning: Color.lerp(warning, other.warning, t)!,
      onWarning: Color.lerp(onWarning, other.onWarning, t)!,
    );
  }
}

/// Per-role badge colors (admin, seller, driver, customer).
@immutable
class RoleBadgeColors extends ThemeExtension<RoleBadgeColors> {
  const RoleBadgeColors({
    required this.adminBg,
    required this.adminFg,
    required this.sellerBg,
    required this.sellerFg,
    required this.driverBg,
    required this.driverFg,
    required this.customerBg,
    required this.customerFg,
  });

  final Color adminBg;
  final Color adminFg;
  final Color sellerBg;
  final Color sellerFg;
  final Color driverBg;
  final Color driverFg;
  final Color customerBg;
  final Color customerFg;

  // Role badges — dark-only palette. `.light` aliases to `.dark` values.
  static const dark = RoleBadgeColors(
    adminBg: Color(0xFF2A0E0E),
    adminFg: Color(0xFFFCA5A5),
    sellerBg: Color(0xFF1F1608),
    sellerFg: Color(0xFFF59E0B),
    driverBg: Color(0xFF0F2A3D),
    driverFg: Color(0xFF7DD3FC),
    customerBg: Color(0xFF0F2A1E),
    customerFg: Color(0xFF86EFAC),
  );

  static const light = dark;

  (Color, Color) forRole(String role) {
    switch (role) {
      case 'admin':
        return (adminBg, adminFg);
      case 'seller':
        return (sellerBg, sellerFg);
      case 'driver':
        return (driverBg, driverFg);
      case 'customer':
      default:
        return (customerBg, customerFg);
    }
  }

  @override
  RoleBadgeColors copyWith({
    Color? adminBg,
    Color? adminFg,
    Color? sellerBg,
    Color? sellerFg,
    Color? driverBg,
    Color? driverFg,
    Color? customerBg,
    Color? customerFg,
  }) =>
      RoleBadgeColors(
        adminBg: adminBg ?? this.adminBg,
        adminFg: adminFg ?? this.adminFg,
        sellerBg: sellerBg ?? this.sellerBg,
        sellerFg: sellerFg ?? this.sellerFg,
        driverBg: driverBg ?? this.driverBg,
        driverFg: driverFg ?? this.driverFg,
        customerBg: customerBg ?? this.customerBg,
        customerFg: customerFg ?? this.customerFg,
      );

  @override
  RoleBadgeColors lerp(ThemeExtension<RoleBadgeColors>? other, double t) {
    if (other is! RoleBadgeColors) return this;
    return RoleBadgeColors(
      adminBg: Color.lerp(adminBg, other.adminBg, t)!,
      adminFg: Color.lerp(adminFg, other.adminFg, t)!,
      sellerBg: Color.lerp(sellerBg, other.sellerBg, t)!,
      sellerFg: Color.lerp(sellerFg, other.sellerFg, t)!,
      driverBg: Color.lerp(driverBg, other.driverBg, t)!,
      driverFg: Color.lerp(driverFg, other.driverFg, t)!,
      customerBg: Color.lerp(customerBg, other.customerBg, t)!,
      customerFg: Color.lerp(customerFg, other.customerFg, t)!,
    );
  }
}

/// BuildContext extension getters for ergonomic theme access.
extension AppThemeContext on BuildContext {
  ColorScheme get colors => Theme.of(this).colorScheme;
  TextTheme get textStyles => Theme.of(this).textTheme;
  AppSemanticColors get semanticColors =>
      Theme.of(this).extension<AppSemanticColors>() ?? AppSemanticColors.light;
  RoleBadgeColors get roleBadgeColors =>
      Theme.of(this).extension<RoleBadgeColors>() ?? RoleBadgeColors.light;
}
