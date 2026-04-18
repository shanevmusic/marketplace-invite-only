import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:marketplace/app/theme/app_theme.dart';
import 'package:marketplace/shared/widgets/app_button.dart';

Widget _wrap(Widget child) => MaterialApp(
      theme: AppTheme.light(),
      home: Scaffold(body: Center(child: child)),
    );

void main() {
  testWidgets('renders label and triggers onPressed', (tester) async {
    var tapped = 0;
    await tester.pumpWidget(_wrap(
      AppButton(label: 'Go', onPressed: () => tapped++),
    ));
    expect(find.text('Go'), findsOneWidget);
    await tester.tap(find.byType(AppButton));
    expect(tapped, 1);
  });

  testWidgets('disabled when onPressed is null', (tester) async {
    await tester.pumpWidget(_wrap(const AppButton(label: 'Nope')));
    // AppButton wraps its content in a Semantics with enabled:!disabled.
    // When onPressed is null, the inner InkWell has onTap:null, so tapping
    // does nothing. Verify by checking the InkWell's onTap.
    final inkWell = tester.widget<InkWell>(find.descendant(
      of: find.byType(AppButton),
      matching: find.byType(InkWell),
    ));
    expect(inkWell.onTap, isNull);
  });

  testWidgets('loading state hides label and prevents tap', (tester) async {
    var tapped = 0;
    await tester.pumpWidget(_wrap(
      AppButton(label: 'Submit', onPressed: () => tapped++, isLoading: true),
    ));
    expect(find.text('Submit'), findsNothing);
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
    await tester.tap(find.byType(AppButton));
    expect(tapped, 0);
  });

  testWidgets('renders all variants without throwing', (tester) async {
    for (final v in AppButtonVariant.values) {
      await tester.pumpWidget(_wrap(
        AppButton(label: v.name, onPressed: () {}, variant: v),
      ));
      expect(find.text(v.name), findsOneWidget);
    }
  });

  testWidgets('renders all sizes without throwing', (tester) async {
    for (final s in AppButtonSize.values) {
      await tester.pumpWidget(_wrap(
        AppButton(label: s.name, onPressed: () {}, size: s),
      ));
      expect(find.text(s.name), findsOneWidget);
    }
  });

  testWidgets('semantics exposes custom label', (tester) async {
    await tester.pumpWidget(_wrap(
      AppButton(
        label: 'X',
        semanticsLabel: 'close dialog',
        onPressed: () {},
      ),
    ));
    final semantics = tester.getSemantics(find.byType(AppButton));
    expect(semantics.label, contains('close dialog'));
  });
}
