class ApiConstants {
  // Sur un émulateur Android standard, 10.0.2.2 redirige vers localhost de la machine hôte.
  // Pour un appareil Android physique, remplacez par l'IP locale du PC (ex: http://192.168.1.50:8000/api/v1).
  static const String baseUrl = 'http://10.0.2.2:8000/api/v1';

  // Auth endpoints
  static const String login = '/auth/login';
  static const String register = '/auth/register';
  static const String forgotPassword = '/auth/forgot-password';

  // Chat & RAG endpoints
  static const String chatMessage = '/chat/message';
  static const String chatEscalate = '/chat/escalate';

  // Tickets endpoints
  static const String tickets = '/tickets/';
  static const String createTicket = '/tickets/create';
  
  // Storage keys
  static const String tokenKey = 'geiser_access_token';
  static const String userKey = 'geiser_user_data';
}
