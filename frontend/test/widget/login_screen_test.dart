import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mocktail/mocktail.dart';

import 'package:marketplace/app/theme/app_theme.dart';
import 'package:marketplace/features/auth/data/auth_dtos.dart';
import 'package:marketplace/features/auth/screens/login_screen.dart';
import 'package:marketplace/features/auth/state/auth_controller.dart';

import '../helpers/mock_auth_api.dart';

Widget _host(MockAuthApi api) => ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(
          TestAuthRepository(api: api),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light(),
        home: const LoginScreen(),
      ),
    );

void main() {
  setUpAll(registerFallbackValues);

  testWidgets('shows email and password inputs', (tester) async {
    final api = MockAuthApi();
    await tester.pumpWidget(_host(api));
    await tester.pump();
    expect(find.text('Email'), findsWidgets);
    expect(find.text('Password'), findsWidgets);
    expect(find.text('Sign in'), findsOneWidget);
  });

  testWidgets('submit disabled until email + password valid', (tester) async {
    final api = MockAuthApi();
    await tester.pumpWidget(_host(api));
    await tester.pump();

    // Fill invalid email, some password.
    await tester.enterText(find.byType(TextField).first, 'not-an-email');
    await tester.enterText(find.byType(TextField).last, 'hunter2');
    await tester.pump();

    // Tap should not call login.
    await tester.tap(find.text('Sign in'));
    await tester.pump();
    verifyNever(() => api.login(any()));

    // Fix email → now valid.
    await tester.enterText(find.byType(TextField).first, 'u@example.com');
    await tester.pump();
    when(() => api.login(any())).thenAnswer((_) async => sampleAuthResponse());
    await tester.tap(find.text('Sign in'));
    await tester.pump();
    verify(() => api.login(any())).called(1);
  });

  testWidgets('invalid credentials shows inline password error',
      (tester) async {
    final api = MockAuthApi();
    when(() => api.login(any())).thenThrow(
      AuthApiException(
        statusCode: 401,
        code: 'INVALID_CREDENTIALS',
        message: 'nope',
      ),
    );

    await tester.pumpWidget(_host(api));
    await tester.pump();
    await tester.enterText(find.byType(TextField).first, 'u@example.com');
    await tester.enterText(find.byType(TextField).last, 'pwpwpwpwpwpw');
    await tester.pump();
    await tester.tap(find.text('Sign in'));
    await tester.pumpAndSettle();

    expect(find.text('Incorrect email or password.'), findsOneWidget);
  });
}
