import 'dart:ui' show Locale;

import 'package:intl/intl.dart';

/// MANDATORY formatter for every rendered amount. See
/// frontend-spec/phase-9-components-diff.md §12. Raw `/ 100` usage or
/// ad-hoc `NumberFormat(...).format(x/100)` calls under `features/**` are
/// forbidden (grep test enforces this).
String formatMoney(
  int minorUnits, {
  String currencyCode = 'USD',
  Locale? locale,
  bool symbol = true,
  int? decimalDigitsOverride,
}) {
  final localeName = locale?.toLanguageTag() ?? 'en_US';
  final fmt = NumberFormat.simpleCurrency(
    name: currencyCode,
    locale: localeName,
    decimalDigits: decimalDigitsOverride,
  );
  final digits = decimalDigitsOverride ?? fmt.decimalDigits ?? 2;
  final divisor = _pow10(digits);
  final value = minorUnits / divisor;
  if (symbol) {
    return fmt.format(value);
  }
  return NumberFormat.decimalPattern(localeName).format(value);
}

/// Power of ten helper without hitting the `/` operator at call sites
/// under features/** (scope of the grep guard).
num _pow10(int digits) {
  var v = 1;
  for (var i = 0; i < digits; i++) {
    v *= 10;
  }
  return v;
}
