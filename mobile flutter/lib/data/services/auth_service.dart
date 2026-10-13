import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/constants/api_constants.dart';
import '../models/user_model.dart';
import 'api_client.dart';

class LoginResult {
  final bool success;
  final bool requires2FA;
  final String? email;
  final String? message;
  final UserModel? user;
  final String? error;

  LoginResult({
    required this.success,
    this.requires2FA = false,
    this.email,
    this.message,
    this.user,
    this.error,
  });

  factory LoginResult.successResult(UserModel user) {
    return LoginResult(
      success: true,
      requires2FA: false,
      user: user,
    );
  }

  factory LoginResult.twoFactorRequired({required String email, String? message}) {
    return LoginResult(
      success: false,
      requires2FA: true,
      email: email,
      message: message,
    );
  }

  factory LoginResult.failure(String error) {
    return LoginResult(
      success: false,
      requires2FA: false,
      error: error,
    );
  }
}

class AuthService {
  final Dio _dio = ApiClient().dio;

  Future<LoginResult> login(String email, String password) async {
    try {
      final response = await _dio.post(
        ApiConstants.login,
        data: {'email': email, 'password': password},
      );

      if (response.statusCode == 200 && response.data != null) {
        final data = response.data;

        // Check if Two-Factor Authentication is triggered
        if (data['requires_2fa'] == true) {
          return LoginResult.twoFactorRequired(
            email: data['email'] ?? email,
            message: data['message'] ?? 'Code de vérification envoyé par e-mail.',
          );
        }

        final token = data['access_token'];
        final refreshToken = data['refresh_token'];
        final userData = data['user'];

        if (token != null && userData != null) {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString(ApiConstants.tokenKey, token);
          if (refreshToken != null) {
            await prefs.setString(ApiConstants.refreshTokenKey, refreshToken);
          }
          await prefs.setString(ApiConstants.userKey, jsonEncode(userData));
          return LoginResult.successResult(UserModel.fromJson(userData));
        }
      }
      return LoginResult.failure('Réponse invalide du serveur');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Identifiants invalides';
      return LoginResult.failure(msg.toString());
    } catch (e) {
      return LoginResult.failure('Erreur de connexion : $e');
    }
  }

  /// Verify 2FA OTP code during login: POST /auth/verify-2fa
  Future<UserModel> verify2FALogin(String email, String code) async {
    try {
      final response = await _dio.post(
        ApiConstants.verify2FA,
        data: {
          'email': email,
          'code': code.trim(),
        },
      );

      if (response.statusCode == 200 && response.data != null) {
        final data = response.data;
        final token = data['access_token'];
        final refreshToken = data['refresh_token'];
        final userData = data['user'];

        if (token != null && userData != null) {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString(ApiConstants.tokenKey, token);
          if (refreshToken != null) {
            await prefs.setString(ApiConstants.refreshTokenKey, refreshToken);
          }
          await prefs.setString(ApiConstants.userKey, jsonEncode(userData));
          return UserModel.fromJson(userData);
        }
      }
      throw Exception('Format de réponse invalide');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Code 2FA invalide ou expiré';
      throw Exception(msg);
    } catch (e) {
      throw Exception('Erreur de validation 2FA : $e');
    }
  }

  Future<UserModel?> register(String email, String password, String fullName) async {
    try {
      final response = await _dio.post(
        ApiConstants.register,
        data: {
          'email': email,
          'password': password,
          'full_name': fullName,
          'role': 'USER',
        },
      );
      if (response.statusCode == 200 || response.statusCode == 201) {
        final loginRes = await login(email, password);
        return loginRes.user;
      }
      return null;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Erreur lors de l\'inscription';
      throw Exception(msg);
    }
  }

  Future<UserModel?> getCurrentUser() async {
    final prefs = await SharedPreferences.getInstance();
    final userJson = prefs.getString(ApiConstants.userKey);
    if (userJson != null) {
      try {
        return UserModel.fromJson(jsonDecode(userJson));
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  Future<void> logout() async {
    final prefs = await SharedPreferences.getInstance();
    try {
      // Invalidate JWT tokens server-side in MongoDB token_blacklist
      await _dio.post('/auth/logout');
    } catch (_) {
      // Always proceed with local logout even if offline or server returns 401
    } finally {
      await prefs.remove(ApiConstants.tokenKey);
      await prefs.remove(ApiConstants.refreshTokenKey);
      await prefs.remove(ApiConstants.userKey);
    }
  }

  // ── 2FA Management ──────────────────────────────────────────────

  /// Returns the current 2FA enabled status for the authenticated user.
  Future<bool> get2FAStatus() async {
    try {
      final response = await _dio.get('/auth/2fa/status');
      return response.data['enabled'] as bool? ?? false;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Failed to fetch 2FA status';
      throw Exception(msg);
    }
  }

  /// Step 1 Enable — Sends a 6-digit OTP to the user's registered email.
  Future<void> requestEnable2FA() async {
    try {
      await _dio.post('/auth/2fa/enable/request');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Failed to send 2FA code';
      throw Exception(msg);
    }
  }

  /// Step 2 Enable — Validates the OTP and enables 2FA.
  Future<void> confirmEnable2FA(String code) async {
    try {
      await _dio.post('/auth/2fa/enable/confirm', data: {'code': code});
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Invalid or expired code';
      throw Exception(msg);
    }
  }

  /// Step 1 Disable — Verifies password then sends OTP.
  Future<void> requestDisable2FA(String password) async {
    try {
      await _dio.post('/auth/2fa/disable/request', data: {'password': password});
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Incorrect password';
      throw Exception(msg);
    }
  }

  /// Step 2 Disable — Validates OTP and disables 2FA.
  Future<void> confirmDisable2FA(String code) async {
    try {
      await _dio.post('/auth/2fa/disable/confirm', data: {'code': code});
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Invalid or expired code';
      throw Exception(msg);
    }
  }
}

/// Static convenience wrapper used by profile_screen.dart
class AuthApiService {
  static final AuthService _svc = AuthService();

  static Future<bool> get2FAStatus() => _svc.get2FAStatus();
  static Future<void> requestEnable2FA() => _svc.requestEnable2FA();
  static Future<void> confirmEnable2FA(String code) => _svc.confirmEnable2FA(code);
  static Future<void> requestDisable2FA(String password) => _svc.requestDisable2FA(password);
  static Future<void> confirmDisable2FA(String code) => _svc.confirmDisable2FA(code);
}
