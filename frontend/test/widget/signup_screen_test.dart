import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:marketplace/app/theme/app_theme.dart';
import 'package:marketplace/features/auth/screens/signup_screen.dart';
import 'package:marketplace/features/auth/state/auth_controller.dart';

import '../helpers/mock_auth_api.dart';

Widget _host(SignupScreenArgs args, MockAuthApi api) => ProviderScope(
      overrides: [
        authRepositoryProvider.overrideWithValue(
          TestAuthRepository(api: api),
        ),
      ],
      child: MaterialApp(
        theme: AppTheme.light(),
        home: SignupScreen(args: args),
      ),
    );

void main() {
  setUpAll(registerFallbackValues);

  testWidgets('shows role choice when roleChoiceRequired', (tester) async {
    await tester.pumpWidget(_host(
      const SignupScreenArgs(
        inviteToken: 't',
        roleChoiceRequired: true,
        inviterName: 'Acme',
      ),
      MockAuthApi(),
    ));
    await tester.pump();
    expect(find.text('Which kind of account do you want?'), findsOneWidget);
    expect(find.text('Customer'), findsOneWidget);
    expect(find.text('Seller'), findsOneWidget);
  });

  testWidgets('hides role choice for admin-style invites', (tester) async {
    await tester.pumpWidget(_host(
      const SignupScreenArgs(inviteToken: 't', roleChoiceRequired: false),
      MockAuthApi(),
    ));
    await tester.pump();
    expect(find.text('Which kind of account do you want?'), findsNothing);
  });

  testWidgets('shows inviter name header when provided', (tester) async {
    await tester.pumpWidget(_host(
      const SignupScreenArgs(inviteToken: 't', inviterName: 'Acme Co'),
      MockAuthApi(),
    ));
    await tester.pump();
    expect(find.textContaining('Acme Co'), findsWidgets);
  });

  testWidgets('password helper mentions 12-char minimum', (tester) async {
    await tester.pumpWidget(_host(
      const SignupScreenArgs(inviteToken: 't'),
      MockAuthApi(),
    ));
    await tester.pump();
    expect(find.text('Minimum 12 characters.'), findsOneWidget);
  });
}
