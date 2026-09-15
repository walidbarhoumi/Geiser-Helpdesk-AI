import 'package:flutter/material.dart';
import '../../data/models/ticket_model.dart';
import '../../data/services/ticket_service.dart';

class TicketProvider extends ChangeNotifier {
  final TicketService _ticketService = TicketService();
  List<TicketModel> _tickets = [];
  bool _isLoading = false;
  String? _error;

  List<TicketModel> get tickets => _tickets;
  bool get isLoading => _isLoading;
  String? get error => _error;

  Future<void> fetchTickets() async {
    _isLoading = true;
    _error = null;
    notifyListeners();
    try {
      _tickets = await _ticketService.fetchUserTickets();
    } catch (e) {
      _error = e.toString().replaceAll('Exception: ', '');
    } finally {
      _isLoading = false;
      notifyListeners();
    }
  }

  Future<bool> createTicket({
    required String subject,
    required String description,
    required String category,
    required String priority,
  }) async {
    _isLoading = true;
    _error = null;
    notifyListeners();
    try {
      final newTicket = await _ticketService.createTicket(
        subject: subject,
        description: description,
        category: category,
        priority: priority,
      );
      _tickets.insert(0, newTicket);
      _isLoading = false;
      notifyListeners();
      return true;
    } catch (e) {
      _error = e.toString().replaceAll('Exception: ', '');
      _isLoading = false;
      notifyListeners();
      return false;
    }
  }
}
