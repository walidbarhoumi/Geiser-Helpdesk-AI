import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ApiConstants {
  // Default tunnel URL or local fallback
  static const String defaultTunnelUrl =
      'https://sharp-msgid-elite-mirror.trycloudflare.com';

  // Android emulator loopback host address to reach host machine
  static const String androidEmulatorHostUrl = 'http://10.0.2.2:8000';

  // In-memory custom tunnel base URL (updated by user or loaded from SharedPreferences)
  static String? _customBaseUrl;

  /// Initialize custom base URL from persistent storage on startup
  static Future<void> initCustomBaseUrl() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final savedUrl = prefs.getString(customUrlKey);
      if (savedUrl != null && savedUrl.trim().isNotEmpty) {
        _customBaseUrl = _sanitizeUrl(savedUrl);
      }
    } catch (_) {}
  }

  /// Get current configured server URL (without /api/v1)
  static String get currentServerUrl {
    if (_customBaseUrl != null && _customBaseUrl!.isNotEmpty) {
      return _customBaseUrl!;
    }
    // For Android emulator, default to host loopback 10.0.2.2 so it works even without active tunnel!
    if (defaultTargetPlatform == TargetPlatform.android) {
      return androidEmulatorHostUrl;
    }
    if (kIsWeb) {
      return 'http://localhost:8000';
    }
    return defaultTunnelUrl;
  }

  /// Update server URL dynamically and persist it
  static Future<void> setCustomServerUrl(String url) async {
    final sanitized = _sanitizeUrl(url);
    _customBaseUrl = sanitized;
    final prefs = await SharedPreferences.getInstance();
    if (sanitized.isNotEmpty) {
      await prefs.setString(customUrlKey, sanitized);
    } else {
      await prefs.remove(customUrlKey);
    }
  }

  static String _sanitizeUrl(String input) {
    var s = input.trim();
    if (s.isEmpty) return '';
    if (!s.startsWith('http://') && !s.startsWith('https://')) {
      s = 'https://$s';
    }
    // Remove trailing slashes and /api/v1 if typed by user
    while (s.endsWith('/')) {
      s = s.substring(0, s.length - 1);
    }
    if (s.endsWith('/api/v1')) {
      s = s.substring(0, s.length - '/api/v1'.length);
    }
    if (s.endsWith('/docs')) {
      s = s.substring(0, s.length - '/docs'.length);
    }
    return s;
  }

  /// Base API URL with /api/v1 prefix
  static String get baseUrl {
    // If user specified a custom URL in login screen, always prioritize it!
    if (_customBaseUrl != null && _customBaseUrl!.isNotEmpty) {
      return '$_customBaseUrl/api/v1';
    }

    if (kIsWeb) {
      return 'http://localhost:8000/api/v1';
    }

    if (defaultTargetPlatform == TargetPlatform.android) {
      // Default to 10.0.2.2 on Android emulator so backend on host is reached directly
      return '$androidEmulatorHostUrl/api/v1';
    }

    if (defaultTargetPlatform == TargetPlatform.iOS) {
      return 'http://localhost:8000/api/v1';
    }

    return '$defaultTunnelUrl/api/v1';
  }

  // Auth endpoints
  static const String login = '/auth/login';
  static const String verify2FA = '/auth/verify-2fa';
  static const String register = '/auth/register';
  static const String forgotPassword = '/auth/forgot-password';

  // Chat & RAG endpoints
  static const String chatMessage = '/chat/message';
  static const String chatEscalate = '/chat/escalate';

  // Tickets endpoints
  static const String tickets = '/tickets/';
  static const String createTicket = '/tickets/create';

  // Admin / management endpoints
  static const String agents = '/agents/';
  static const String teams = '/teams/';
  static const String users = '/users/';
  static const String notifications = '/notifications/';
  static const String notificationsHistory = '/notifications/history';
  static const String analyticsDB = '/analytics/dashboard';
  static const String slaAlerts = '/sla/alerts';
  static const String slaRisk = '/sla/risk';
  static const String auditLogs = '/audit/logs';

  // Storage keys
  static const String tokenKey = 'geiser_access_token';
  static const String refreshTokenKey = 'geiser_refresh_token';
  static const String userKey = 'geiser_user_data';
  static const String customUrlKey = 'geiser_custom_server_url';
}
