// Phase-10 killed 30s polling for order/delivery detail. Fail the build if
// `Timer.periodic` reappears under orders/** or tracking/**.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('no Timer.periodic under orders/** or tracking/**', () {
    final roots = [
      Directory('lib/features/orders'),
      Directory('lib/features/tracking'),
    ];
    final violations = <String>[];
    final re = RegExp(r'Timer\.periodic\s*\(');
    for (final dir in roots) {
      if (!dir.existsSync()) continue;
      for (final f in dir
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'))) {
        final src = f.readAsStringSync();
        final cleaned = src
            .split('\n')
            .where((l) => !l.trimLeft().startsWith('//'))
            .join('\n');
        if (re.hasMatch(cleaned)) {
          violations.add(f.path);
        }
      }
    }
    expect(violations, isEmpty,
        reason: 'Phase-10 removed polling; use the WS client instead. '
            'Violators:\n${violations.join('\n')}');
  });
}
