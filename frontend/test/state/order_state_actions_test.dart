import 'package:flutter_test/flutter_test.dart';
import 'package:marketplace/features/orders/seller/widgets/order_state_action_panel.dart';

void main() {
  group('orderActionsForStatus', () {
    test('pending → Accept + Cancel', () {
      final a = orderActionsForStatus('pending');
      expect(a.map((e) => e.action), ['accept', 'cancel']);
      expect(a.last.destructive, isTrue);
    });
    test('accepted → Start preparing + Cancel', () {
      final a = orderActionsForStatus('accepted');
      expect(a.map((e) => e.action), ['preparing', 'cancel']);
    });
    test('preparing → Self-deliver + Request driver', () {
      final a = orderActionsForStatus('preparing');
      expect(a.map((e) => e.action), ['self-deliver', 'request-driver']);
    });
    test('out_for_delivery → Mark delivered', () {
      final a = orderActionsForStatus('out_for_delivery');
      expect(a.map((e) => e.action), ['delivered']);
    });
    test('delivered → Complete', () {
      final a = orderActionsForStatus('delivered');
      expect(a.map((e) => e.action), ['complete']);
    });
    test('cancelled and completed → no actions', () {
      expect(orderActionsForStatus('cancelled'), isEmpty);
      expect(orderActionsForStatus('completed'), isEmpty);
    });
  });
}
