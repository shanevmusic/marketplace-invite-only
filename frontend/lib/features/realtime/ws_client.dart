import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../../data/api/api_config.dart';
import '../auth/data/auth_repository.dart';
import '../auth/state/auth_controller.dart';
import 'realtime_status.dart';
import 'ws_event.dart';

typedef WsChannelFactory = WebSocketChannel Function(Uri uri);

WebSocketChannel _defaultFactory(Uri uri) => WebSocketChannel.connect(uri);

/// Channel helpers. Public so feature code can build names without re-deriving.
String conversationChannel(String id) => 'conversation:$id';
String deliveryChannel(String id) => 'delivery:$id';

const _backoffSteps = <int>[1, 2, 4, 8, 16, 30, 60];

/// Sole WebSocket gateway. One socket per session, multiplexes channels.
/// Receive-only for application payloads; outbound is limited to control
/// frames (subscribe/unsubscribe/ping/typing).
class WsClient {
  WsClient({
    required this.getToken,
    WsChannelFactory? channelFactory,
    Duration heartbeatInterval = const Duration(seconds: 30),
    Duration pongTimeout = const Duration(seconds: 30),
    Random? random,
  })  : _factory = channelFactory ?? _defaultFactory,
        _heartbeat = heartbeatInterval,
        _pongTimeout = pongTimeout,
        _rand = random ?? Random();

  final Future<String?> Function() getToken;
  final WsChannelFactory _factory;
  final Duration _heartbeat;
  final Duration _pongTimeout;
  final Random _rand;

  final _eventsCtl = StreamController<WsEvent>.broadcast();
  final _statusCtl = StreamController<RealtimeStatus>.broadcast();
  final _deniedCtl = StreamController<SubscriptionDeniedEvent>.broadcast();
  final Set<String> _desired = <String>{};

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _sub;
  Timer? _heartbeatTimer;
  Timer? _pongTimer;
  Timer? _reconnectTimer;
  int _missedPongs = 0;
  int _attempt = 0;
  RealtimeStatus _status = RealtimeStatus.disconnected;
  bool _disposed = false;

  Stream<WsEvent> get events => _eventsCtl.stream;
  Stream<RealtimeStatus> get status => _statusCtl.stream;
  Stream<SubscriptionDeniedEvent> get denied => _deniedCtl.stream;
  RealtimeStatus get currentStatus => _status;
  Set<String> get desiredChannels => Set.unmodifiable(_desired);

  Future<void> connect() async {
    if (_disposed) return;
    if (_status == RealtimeStatus.connected ||
        _status == RealtimeStatus.connecting) {
      return;
    }
    _setStatus(RealtimeStatus.connecting);
    final token = await getToken();
    if (token == null || token.isEmpty) {
      _setStatus(RealtimeStatus.unauthorized);
      return;
    }
    final uri = _buildUri(token);
    try {
      final ch = _factory(uri);
      _channel = ch;
      _sub = ch.stream.listen(
        _onRaw,
        onError: (Object e, StackTrace st) => _onClose(code: 1006),
        onDone: () => _onClose(code: ch.closeCode ?? 1006),
        cancelOnError: true,
      );
      _attempt = 0;
      _missedPongs = 0;
      _setStatus(RealtimeStatus.connected);
      _startHeartbeat();
      _replaySubscriptions();
    } catch (_) {
      _onClose(code: 1006);
    }
  }

  void subscribe(String channel) {
    _desired.add(channel);
    if (_status == RealtimeStatus.connected) {
      _send({'type': 'subscribe', 'channel': channel});
    }
  }

  void unsubscribe(String channel) {
    _desired.remove(channel);
    if (_status == RealtimeStatus.connected) {
      _send({'type': 'unsubscribe', 'channel': channel});
    }
  }

  /// Debounced caller supplies cadence; this method just writes to the wire.
  void sendTyping(String conversationId, bool isTyping) {
    if (_status != RealtimeStatus.connected) return;
    _send({
      'type': 'typing',
      'conversation_id': conversationId,
      'is_typing': isTyping,
    });
  }

  Future<void> dispose() async {
    _disposed = true;
    _reconnectTimer?.cancel();
    _heartbeatTimer?.cancel();
    _pongTimer?.cancel();
    _desired.clear();
    final ch = _channel;
    _channel = null;
    await _sub?.cancel();
    _sub = null;
    await ch?.sink.close(1000);
    _setStatus(RealtimeStatus.disconnected);
    await _eventsCtl.close();
    await _statusCtl.close();
    await _deniedCtl.close();
  }

  // ---- internals ----

  Uri _buildUri(String token) {
    final base = Uri.parse(ApiConfig.baseUrl);
    final scheme = base.scheme == 'https' ? 'wss' : 'ws';
    return Uri(
      scheme: scheme,
      host: base.host,
      port: base.hasPort ? base.port : null,
      path: '/ws',
      queryParameters: {'token': token},
    );
  }

  void _send(Map<String, dynamic> msg) {
    final ch = _channel;
    if (ch == null) return;
    try {
      ch.sink.add(jsonEncode(msg));
    } catch (_) {
      // socket dying; let close handler reconnect.
    }
  }

  void _replaySubscriptions() {
    for (final c in _desired) {
      _send({'type': 'subscribe', 'channel': c});
    }
  }

  void _onRaw(dynamic raw) {
    if (raw is! String) return;
    Map<String, dynamic> json;
    try {
      json = jsonDecode(raw) as Map<String, dynamic>;
    } catch (_) {
      return;
    }
    final type = json['type'] as String?;
    switch (type) {
      case 'pong':
        _missedPongs = 0;
        _pongTimer?.cancel();
        return;
      case 'subscribed':
        return;
      case 'error':
        final code = json['code'] as String?;
        final ch = json['channel'] as String?;
        if (code == 'channel.forbidden' && ch != null) {
          _desired.remove(ch);
          _deniedCtl.add(SubscriptionDeniedEvent(ch));
        }
        return;
      case null:
      case 'unknown':
        return;
      default:
        _eventsCtl.add(WsEvent.fromJson(json));
    }
  }

  void _startHeartbeat() {
    _heartbeatTimer?.cancel();
    _heartbeatTimer = Timer.periodic(_heartbeat, (_) => _tickHeartbeat());
  }

  void _tickHeartbeat() {
    if (_status != RealtimeStatus.connected) return;
    _send({'type': 'ping'});
    _pongTimer?.cancel();
    _pongTimer = Timer(_pongTimeout, () {
      _missedPongs++;
      if (_missedPongs >= 2) {
        _onClose(code: 1006);
      }
    });
  }

  void _onClose({required int code}) {
    _heartbeatTimer?.cancel();
    _pongTimer?.cancel();
    final ch = _channel;
    _channel = null;
    _sub?.cancel();
    _sub = null;
    try {
      ch?.sink.close();
    } catch (_) {}
    if (_disposed) return;

    switch (code) {
      case 4401:
        _setStatus(RealtimeStatus.unauthorized);
        return;
      case 4001:
        // Server says auth expired; fall through to reconnect after refresh.
        _scheduleReconnect();
        return;
      case 1000:
        _setStatus(RealtimeStatus.disconnected);
        return;
      default:
        _scheduleReconnect();
    }
  }

  void _scheduleReconnect() {
    _setStatus(RealtimeStatus.reconnecting);
    final delay = _nextDelay(_attempt);
    _attempt++;
    _reconnectTimer?.cancel();
    _reconnectTimer = Timer(delay, connect);
  }

  Duration _nextDelay(int attempt) {
    final idx = attempt.clamp(0, _backoffSteps.length - 1);
    final s = _backoffSteps[idx];
    final millis = _rand.nextInt(s * 1000) + (s * 500);
    return Duration(milliseconds: millis);
  }

  void _setStatus(RealtimeStatus s) {
    if (_status == s) return;
    _status = s;
    _statusCtl.add(s);
  }
}

/// Riverpod provider. Late-bound to the current auth session — disposes the
/// socket on logout via Riverpod's ref.onDispose.
final wsClientProvider = Provider<WsClient>((ref) {
  final repo = ref.read(authRepositoryProvider);
  final client = WsClient(
    getToken: () async {
      final session = ref.read(authControllerProvider).valueOrNull;
      if (session == null) return null;
      return repo.currentAccessToken();
    },
  );
  // Eagerly connect once a session exists.
  ref.listen<AsyncValue<AuthSession?>>(authControllerProvider, (prev, next) {
    final s = next.valueOrNull;
    if (s != null) {
      client.connect();
    }
  });
  ref.onDispose(client.dispose);
  return client;
});
