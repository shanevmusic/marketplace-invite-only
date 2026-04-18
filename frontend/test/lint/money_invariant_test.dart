// Enforces the Phase 9 money invariant: no file under lib/features/** may
// divide by 100 or call `NumberFormat(` directly. All money formatting must
// flow through `lib/shared/format/money.dart`.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('features/** does not divide by 100 or call NumberFormat(', () {
    final featuresDir = Directory('lib/features');
    expect(featuresDir.existsSync(), isTrue, reason: 'run from frontend/');

    final violations = <String>[];
    final files = featuresDir
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'));

    final divRegex = RegExp(r'/\s*100\b');
    final nfRegex = RegExp(r'\bNumberFormat\s*\(');

    for (final f in files) {
      final path = f.path.replaceAll('\\', '/');
      final src = f.readAsStringSync();
      final lines = src.split('\n');
      for (var i = 0; i < lines.length; i++) {
        final l = lines[i];
        if (l.trimLeft().startsWith('//')) continue;
        if (divRegex.hasMatch(l)) {
          violations.add('$path:${i + 1}  / 100');
        }
        if (nfRegex.hasMatch(l)) {
          violations.add('$path:${i + 1}  NumberFormat(');
        }
      }
    }
    expect(
      violations,
      isEmpty,
      reason:
          'Use formatMoney() from lib/shared/format/money.dart instead:\n${violations.join('\n')}',
    );
  });
}
