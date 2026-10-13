import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../core/theme/app_theme.dart';
import '../../core/constants/api_constants.dart';
import '../../data/services/api_client.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool _loading = true;
  String? _error;
  List<dynamic> _notifs = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() { _loading = true; _error = null; });
    try {
      final res = await ApiClient().dio.get(ApiConstants.notificationsHistory);
      _notifs = res.data is List ? res.data as List<dynamic> : [];
    } catch (_) {
      try {
        final res2 = await ApiClient().dio.get(ApiConstants.notifications);
        _notifs = res2.data is List ? res2.data as List<dynamic> : [];
      } catch (e) {
        _error = 'Impossible de charger les notifications';
      }
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Notifications', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
          Text('Historique des alertes', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        ]),
        actions: [
          IconButton(icon: const Icon(Icons.refresh_rounded, size: 22), onPressed: _fetch),
          const SizedBox(width: 8),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Icon(Icons.notifications_off_rounded, color: AppTheme.error, size: 48),
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: AppTheme.textSecondary)),
                  const SizedBox(height: 12),
                  ElevatedButton(onPressed: _fetch, child: const Text('Réessayer')),
                ]))
              : _notifs.isEmpty
                  ? const Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Icon(Icons.notifications_none_rounded, color: AppTheme.textMuted, size: 56),
                      SizedBox(height: 12),
                      Text('Aucune notification', style: TextStyle(color: AppTheme.textSecondary, fontSize: 14)),
                      SizedBox(height: 4),
                      Text('Vous n\'avez aucune notification pour l\'instant.',
                        style: TextStyle(color: AppTheme.textMuted, fontSize: 12)),
                    ]))
                  : RefreshIndicator(
                      onRefresh: _fetch, color: AppTheme.primaryLight,
                      child: ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
                        itemCount: _notifs.length,
                        itemBuilder: (context, i) {
                          final n = _notifs[i] as Map<String, dynamic>;
                          final type = (n['type'] as String? ?? 'SYSTEM').toUpperCase();
                          final title = n['title'] as String? ?? n['subject'] as String? ?? 'Notification';
                          final message = n['message'] as String? ?? n['body'] as String? ?? '';
                          final status = (n['status'] as String? ?? 'SENT').toUpperCase();
                          final createdAt = n['created_at'] as String?;

                          String dateStr = '';
                          if (createdAt != null) {
                            try {
                              dateStr = DateFormat('dd/MM/yyyy HH:mm').format(DateTime.parse(createdAt));
                            } catch (_) {}
                          }

                          Color statusColor;
                          String statusLabel;
                          switch (status) {
                            case 'SENT': statusColor = AppTheme.success; statusLabel = 'Envoyé'; break;
                            case 'FAILED': statusColor = AppTheme.error; statusLabel = 'Échoué'; break;
                            case 'PENDING': statusColor = AppTheme.warning; statusLabel = 'En attente'; break;
                            default: statusColor = AppTheme.textMuted; statusLabel = status;
                          }

                          IconData typeIcon;
                          Color typeColor;
                          switch (type) {
                            case 'EMAIL': typeIcon = Icons.email_rounded; typeColor = AppTheme.info; break;
                            case 'SMS': typeIcon = Icons.phone_android_rounded; typeColor = AppTheme.success; break;
                            case 'PUSH': typeIcon = Icons.notifications_active_rounded; typeColor = const Color(0xFF8B5CF6); break;
                            default: typeIcon = Icons.notifications_rounded; typeColor = AppTheme.warning;
                          }

                          return Container(
                            margin: const EdgeInsets.only(bottom: 10),
                            decoration: BoxDecoration(
                              color: AppTheme.surface,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: const Color(0xFF1F293D)),
                              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.15), blurRadius: 8, offset: const Offset(0, 3))],
                            ),
                            padding: const EdgeInsets.all(14),
                            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                              Container(
                                width: 40, height: 40,
                                decoration: BoxDecoration(color: typeColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(12),
                                  border: Border.all(color: typeColor.withValues(alpha: 0.25))),
                                child: Icon(typeIcon, color: typeColor, size: 20),
                              ),
                              const SizedBox(width: 12),
                              Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                Row(children: [
                                  Expanded(child: Text(title,
                                    style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w700, fontSize: 13),
                                    maxLines: 1, overflow: TextOverflow.ellipsis)),
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                                    decoration: BoxDecoration(color: statusColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6),
                                      border: Border.all(color: statusColor.withValues(alpha: 0.3))),
                                    child: Text(statusLabel, style: TextStyle(color: statusColor, fontSize: 10, fontWeight: FontWeight.bold)),
                                  ),
                                ]),
                                const SizedBox(height: 4),
                                if (message.isNotEmpty)
                                  Text(message,
                                    maxLines: 2, overflow: TextOverflow.ellipsis,
                                    style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12, height: 1.35)),
                                const SizedBox(height: 6),
                                Row(children: [
                                  Container(
                                    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                    decoration: BoxDecoration(color: typeColor.withValues(alpha: 0.08), borderRadius: BorderRadius.circular(4)),
                                    child: Text(type, style: TextStyle(color: typeColor, fontSize: 10, fontWeight: FontWeight.w600)),
                                  ),
                                  const Spacer(),
                                  Text(dateStr, style: const TextStyle(color: AppTheme.textMuted, fontSize: 11)),
                                ]),
                              ])),
                            ]),
                          );
                        },
                      ),
                    ),
    );
  }
}
