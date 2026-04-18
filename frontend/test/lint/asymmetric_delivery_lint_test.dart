// Enforces ADR-0014 at the repository level: no file under a `customer/`
// directory may import anything from an `internal/` directory, and vice
// versa. Runs as a normal `flutter test` — no custom_lint plugin required.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('no customer/internal cross-imports (ADR-0014)', () {
    final libDir = Directory('lib');
    expect(libDir.existsSync(), isTrue, reason: 'run from frontend/');

    final violations = <String>[];
    final files = libDir
        .listSync(recursive: true)
        .whereType<File>()
        .where((f) => f.path.endsWith('.dart'));

    for (final f in files) {
      final path = f.path.replaceAll('\\', '/');
      final isCustomer = path.contains('/customer/');
      final isInternal = path.contains('/internal/');
      if (!isCustomer && !isInternal) continue;

      final src = f.readAsStringSync();
      final importRegex =
          RegExp(r'''^\s*import\s+['"]([^'"]+)['"]''', multiLine: true);
      for (final m in importRegex.allMatches(src)) {
        final imp = m.group(1)!;
        if (isCustomer && imp.contains('/internal/')) {
          violations.add('$path imports $imp (customer -> internal)');
        }
        if (isInternal && imp.contains('/customer/')) {
          violations.add('$path imports $imp (internal -> customer)');
        }
      }
    }
    expect(violations, isEmpty,
        reason: 'ADR-0014 asymmetric delivery visibility violated:\n'
            '${violations.join('\n')}');
  });
}
