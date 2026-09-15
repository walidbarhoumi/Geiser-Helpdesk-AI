import 'package:flutter/material.dart';
import '../../data/models/chat_message_model.dart';
import '../../data/services/chat_service.dart';

class ChatProvider extends ChangeNotifier {
  final ChatService _chatService = ChatService();
  final List<ChatMessageModel> _messages = [];
  bool _isSending = false;
  String? _lastEscalateTicketId;

  List<ChatMessageModel> get messages => _messages;
  bool get isSending => _isSending;
  String? get lastEscalateTicketId => _lastEscalateTicketId;

  ChatProvider() {
    // Message de bienvenue initial
    _messages.add(
      ChatMessageModel(
        role: 'assistant',
        content: 'Bonjour ! Je suis l assistant IA de support GEISER (FAISS + RAG). Décrivez-moi votre problème technique.',
        suggestedActions: [
          'Mot de passe refusé au login',
          'Mon compte AD est verrouillé',
          'Problème de connexion VPN',
          'Mon imprimante est hors ligne',
        ],
        canEscalate: false,
        source: 'knowledge_base',
      ),
    );
  }

  Future<void> sendMessage(String text) async {
    if (text.trim().isEmpty) return;

    final userMsg = ChatMessageModel(
      role: 'user',
      content: text.trim(),
    );
    _messages.add(userMsg);
    _isSending = true;
    notifyListeners();

    try {
      final assistantMsg = await _chatService.sendMessage(_messages);
      _messages.add(assistantMsg);
    } catch (e) {
      _messages.add(
        ChatMessageModel(
          role: 'assistant',
          content: 'Désolé, une erreur est survenue lors de la communication avec l assistant : $e',
          canEscalate: true,
        ),
      );
    } finally {
      _isSending = false;
      notifyListeners();
    }
  }

  Future<bool> escalateToTicket({String? customSubject}) async {
    _isSending = true;
    notifyListeners();
    try {
      final ticket = await _chatService.escalateToTicket(
        messages: _messages,
        customSubject: customSubject,
      );
      _lastEscalateTicketId = ticket['id'] ?? ticket['_id'];
      _messages.add(
        ChatMessageModel(
          role: 'assistant',
          content: 'Votre ticket a été créé avec succès sous la référence #${_lastEscalateTicketId?.substring(0, 6).toUpperCase()}. Un technicien N2 prend en charge votre demande.',
          canEscalate: false,
        ),
      );
      _isSending = false;
      notifyListeners();
      return true;
    } catch (e) {
      _messages.add(
        ChatMessageModel(
          role: 'assistant',
          content: 'Échec de la création du ticket : $e',
        ),
      );
      _isSending = false;
      notifyListeners();
      return false;
    }
  }

  void clearMessages() {
    _messages.clear();
    _messages.add(
      ChatMessageModel(
        role: 'assistant',
        content: 'Nouvelle session démarrée. Comment puis-je vous assister aujourd hui ?',
        suggestedActions: [
          'Mot de passe refusé au login',
          'Mon compte AD est verrouillé',
          'Problème de connexion VPN',
        ],
      ),
    );
    notifyListeners();
  }
}
