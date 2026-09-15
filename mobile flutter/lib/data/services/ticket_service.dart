import 'package:dio/dio.dart';
import '../../core/constants/api_constants.dart';
import '../models/ticket_model.dart';
import 'api_client.dart';

class TicketService {
  final Dio _dio = ApiClient().dio;

  Future<List<TicketModel>> fetchUserTickets() async {
    try {
      final response = await _dio.get(ApiConstants.tickets);
      if (response.statusCode == 200 && response.data is List) {
        return (response.data as List)
            .map((item) => TicketModel.fromJson(item))
            .toList();
      }
      return [];
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Erreur lors du chargement des tickets';
      throw Exception(msg);
    }
  }

  Future<TicketModel> createTicket({
    required String subject,
    required String description,
    required String category,
    required String priority,
  }) async {
    try {
      final response = await _dio.post(
        ApiConstants.createTicket,
        data: {
          'subject': subject,
          'description': description,
          'category': category,
          'priority': priority,
          'channel': 'CHAT',
        },
      );
      return TicketModel.fromJson(response.data);
    } on DioException catch (e) {
      final msg = e.response?.data?['detail'] ?? 'Erreur création ticket';
      throw Exception(msg);
    }
  }
}
