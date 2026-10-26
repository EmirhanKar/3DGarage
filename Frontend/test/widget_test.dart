import 'package:flutter_test/flutter_test.dart';
import 'package:_3dgarage/main.dart';

void main() {
  testWidgets('App smoke test', (WidgetTester tester) async {
    await tester.pumpWidget(const ArabaApp());
    expect(find.byType(ArabaApp), findsOneWidget);
    await tester.pump(const Duration(seconds: 3));
  });
}
