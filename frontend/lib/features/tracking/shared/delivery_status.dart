/// Role-agnostic status + human labels. Lives under `shared/` and may be
/// imported from either customer/ or driver/seller/. ADR-0014 grep test
/// forbids coordinate tokens here.
enum TrackingDeliveryStatus {
  pending,
  accepted,
  preparing,
  outForDelivery,
  delivered,
  completed,
  cancelled,
}

TrackingDeliveryStatus parseStatus(String raw) {
  switch (raw) {
    case 'pending':
      return TrackingDeliveryStatus.pending;
    case 'accepted':
      return TrackingDeliveryStatus.accepted;
    case 'preparing':
      return TrackingDeliveryStatus.preparing;
    case 'out_for_delivery':
      return TrackingDeliveryStatus.outForDelivery;
    case 'delivered':
      return TrackingDeliveryStatus.delivered;
    case 'completed':
      return TrackingDeliveryStatus.completed;
    case 'cancelled':
      return TrackingDeliveryStatus.cancelled;
    default:
      return TrackingDeliveryStatus.pending;
  }
}

String statusHeadline(TrackingDeliveryStatus s) {
  switch (s) {
    case TrackingDeliveryStatus.pending:
      return 'Waiting for seller';
    case TrackingDeliveryStatus.accepted:
      return 'Order accepted';
    case TrackingDeliveryStatus.preparing:
      return 'Preparing your order';
    case TrackingDeliveryStatus.outForDelivery:
      return 'Out for delivery';
    case TrackingDeliveryStatus.delivered:
      return 'Delivered';
    case TrackingDeliveryStatus.completed:
      return 'Completed';
    case TrackingDeliveryStatus.cancelled:
      return 'Cancelled';
  }
}

String etaCopy(int? etaSeconds) {
  if (etaSeconds == null) return 'Arrival time not available yet';
  if (etaSeconds <= 60) return 'Arriving any minute';
  if (etaSeconds < 60 * 60) {
    final m = (etaSeconds / 60).round();
    return 'Arriving in ~$m min';
  }
  final h = (etaSeconds / 3600).floor();
  final remainderMinutes = ((etaSeconds - h * 3600) / 60).round();
  return 'Arriving in ~$h h $remainderMinutes min';
}
