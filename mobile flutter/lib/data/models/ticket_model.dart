class TicketModel {
  final String id;
  final String subject;
  final String description;
  final String category;
  final String? subcategory;
  final String priority;
  final String status;
  final String channel;
  final String userId;
  final String? resolutionNote;
  final DateTime createdAt;
  final DateTime updatedAt;

  TicketModel({
    required this.id,
    required this.subject,
    required this.description,
    required this.category,
    this.subcategory,
    required this.priority,
    required this.status,
    required this.channel,
    required this.userId,
    this.resolutionNote,
    required this.createdAt,
    required this.updatedAt,
  });

  factory TicketModel.fromJson(Map<String, dynamic> json) {
    return TicketModel(
      id: json['id'] ?? json['_id'] ?? '',
      subject: json['subject'] ?? 'Sans titre',
      description: json['description'] ?? '',
      category: json['category'] ?? 'Général',
      subcategory: json['subcategory'],
      priority: json['priority'] ?? 'LOW',
      status: json['status'] ?? 'OPEN',
      channel: json['channel'] ?? 'WEB',
      userId: json['user_id'] ?? '',
      resolutionNote: json['resolution_note'],
      createdAt: DateTime.tryParse(json['created_at'] ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] ?? '') ?? DateTime.now(),
    );
  }
}
