import 'dart:convert';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../../core/constants/api_constants.dart';
import '../models/user_model.dart';
import 'api_client.dart';

class AuthService {
  final Dio _dio = ApiClient().dio;

  Future<UserModel?> login(String email, String password) async {
    try {
      final response = await _dio.post(
        ApiConstants.login,
        data: {'email': email, 'password': password},
      );

      if (response.statusCode == 200 && response.data != null) {
        final data = response.data;
        final token = data['access_token'];
        final userData = data['user'];

        if (token != null && userData != null) {
          final prefs = await SharedPreferences.getInstance();
          await prefs.setString(ApiConstants.tokenKey, token);
          await prefs.setString(ApiConstants.userKey, jsonEncode(userData));
          return UserModel.fromJson(userData);
        }
      }
      return null;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Identifiants invalides';
      throw Exception(msg);
    } catch (e) {
      throw Exception('Erreur de connexion : $e');
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
        return await login(email, password);
      }
      return null;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Erreur lors de l inscription';
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
    await prefs.remove(ApiConstants.tokenKey);
    await prefs.remove(ApiConstants.userKey);
  }
}
