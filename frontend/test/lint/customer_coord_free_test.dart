// Enforces ADR-0014 at the token level. No source under
// lib/features/orders/customer/** or lib/features/tracking/customer/**
// may reference coordinate, driver identity, seller geo, or breadcrumb
// tokens. If this test fails, the customer side has picked up a field it
// must not see.
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';

void main() {
  test('customer side never references coordinates or driver identity', () {
    final roots = [
      Directory('lib/features/orders/customer'),
      Directory('lib/features/tracking/customer'),
      Directory('lib/features/delivery/customer'),
    ];

    final forbidden = [
      RegExp(r'\blat\b'),
      RegExp(r'\blng\b'),
      RegExp(r'\blatitude\b'),
      RegExp(r'\blongitude\b'),
      RegExp(r'\bdriver_id\b'),
      RegExp(r'\bdriverId\b'),
      RegExp(r'\bseller_lat\b'),
      RegExp(r'\bseller_lng\b'),
      RegExp(r'\bbreadcrumbs\b'),
      RegExp(r'\bdistance_meters\b'),
      RegExp(r'\bdistanceMeters\b'),
    ];

    final violations = <String>[];
    for (final dir in roots) {
      if (!dir.existsSync()) continue;
      final files = dir
          .listSync(recursive: true)
          .whereType<File>()
          .where((f) => f.path.endsWith('.dart'));
      for (final f in files) {
        final path = f.path.replaceAll('\\', '/');
        final src = f.readAsStringSync();
        // Strip out line comments & block comments so narrative text in
        // banner comments does not trigger the guard.
        final withoutLineComments =
            src.split('\n').where((l) => !l.trimLeft().startsWith('//')).join('\n');
        for (final r in forbidden) {
          if (r.hasMatch(withoutLineComments)) {
            violations.add('$path matches ${r.pattern}');
          }
        }
      }
    }
    expect(
      violations,
      isEmpty,
      reason:
          'ADR-0014 violated: customer/** must not reference coordinates, driver id, or breadcrumbs.\n${violations.join('\n')}',
    );
  });
}
