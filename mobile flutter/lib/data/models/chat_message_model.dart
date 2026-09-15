class ChatMessageModel {
  final String role; // 'user', 'assistant', 'system'
  final String content;
  final DateTime createdAt;
  final List<String>? suggestedActions;
  final bool canEscalate;
  final String? source;

  ChatMessageModel({
    required this.role,
    required this.content,
    DateTime? createdAt,
    this.suggestedActions,
    this.canEscalate = false,
    this.source,
  }) : createdAt = createdAt ?? DateTime.now();

  factory ChatMessageModel.fromJson(Map<String, dynamic> json) {
    return ChatMessageModel(
      role: json['role'] ?? 'assistant',
      content: json['content'] ?? json['reply'] ?? '',
      createdAt: json['created_at'] != null ? DateTime.tryParse(json['created_at']) : null,
      suggestedActions: (json['suggested_actions'] as List<dynamic>?)
          ?.map((e) => e.toString())
          .toList(),
      canEscalate: json['can_escalate'] ?? false,
      source: json['source'],
    );
  }

  Map<String, dynamic> toApiJson() {
    return {
      'role': role,
      'content': content,
      'created_at': createdAt.toIso8601String(),
    };
  }
}
