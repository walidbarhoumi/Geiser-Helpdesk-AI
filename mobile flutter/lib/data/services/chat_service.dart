import 'package:dio/dio.dart';
import '../../core/constants/api_constants.dart';
import '../models/chat_message_model.dart';
import 'api_client.dart';

class ChatService {
  final Dio _dio = ApiClient().dio;

  Future<ChatMessageModel> sendMessage(List<ChatMessageModel> messages) async {
    try {
      final apiMessages = messages.map((m) => m.toApiJson()).toList();
      final response = await _dio.post(
        ApiConstants.chatMessage,
        data: {
          'messages': apiMessages,
        },
      );

      if (response.statusCode == 200 && response.data != null) {
        final data = response.data;
        return ChatMessageModel(
          role: 'assistant',
          content: data['reply'] ?? '',
          suggestedActions: (data['suggested_actions'] as List<dynamic>?)
              ?.map((e) => e.toString())
              .toList(),
          canEscalate: data['can_escalate'] ?? false,
          source: data['source'],
        );
      }
      throw Exception('Format de réponse invalide');
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Erreur lors de la communication avec l IA';
      throw Exception(msg);
    } catch (e) {
      throw Exception('Erreur : $e');
    }
  }

  Future<Map<String, dynamic>> escalateToTicket({
    required List<ChatMessageModel> messages,
    String? customSubject,
  }) async {
    try {
      final apiMessages = messages.map((m) => m.toApiJson()).toList();
      final response = await _dio.post(
        ApiConstants.chatEscalate,
        data: {
          'messages': apiMessages,
          'custom_subject': customSubject,
        },
      );
      return response.data;
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Impossible de créer le ticket';
      throw Exception(msg);
    }
  }
}
