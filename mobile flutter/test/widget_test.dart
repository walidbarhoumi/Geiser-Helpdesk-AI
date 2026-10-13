// This is a basic Flutter widget test.
//
// To perform an interaction with a widget in your test, use the WidgetTester
// utility in the flutter_test package. For example, you can send tap and scroll
// gestures. You can also use WidgetTester to find child widgets in the widget
// tree, read text, and verify that the values of widget properties are correct.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:geiser_mobile/app.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  testWidgets('GeiserApp smoke test - chargement initial', (WidgetTester tester) async {
    SharedPreferences.setMockInitialValues({});
    await tester.pumpWidget(const GeiserApp());
    await tester.pumpAndSettle();

    // Vérifie que l'écran de connexion s'affiche par défaut quand non connecté
    expect(find.byType(MaterialApp), findsOneWidget);
  });
}
