import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../core/theme/app_theme.dart';
import '../../core/constants/api_constants.dart';
import '../../data/services/api_client.dart';
import '../providers/auth_provider.dart';

class TicketDetailScreen extends StatefulWidget {
  final String ticketId;

  const TicketDetailScreen({
    super.key,
    required this.ticketId,
  });

  @override
  State<TicketDetailScreen> createState() => _TicketDetailScreenState();
}

class _TicketDetailScreenState extends State<TicketDetailScreen> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _ticket;
  List<dynamic> _agents = [];
  bool _updating = false;

  @override
  void initState() {
    super.initState();
    _fetchTicket();
  }

  Future<void> _fetchTicket() async {
    final role = context.read<AuthProvider>().currentUser?.role;

    setState(() {
      _loading = true;
      _error = null;
    });

    try {
      final res = await ApiClient().dio.get('${ApiConstants.tickets}${widget.ticketId}');
      _ticket = res.data as Map<String, dynamic>?;

      if (role == 'ADMIN' || role == 'AGENT') {
        try {
          final agentsRes = await ApiClient().dio.get(ApiConstants.agents);
          if (agentsRes.data is List) {
            _agents = agentsRes.data as List<dynamic>;
          }
        } catch (_) {}
      }
    } catch (e) {
      _error = 'Impossible de charger les détails du ticket';
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  Future<void> _updateStatus(String newStatus) async {
    setState(() => _updating = true);
    try {
      await ApiClient().dio.put(
        '${ApiConstants.tickets}${widget.ticketId}/status',
        data: {'status': newStatus},
      );
      await _fetchTicket();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Statut mis à jour avec succès')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Erreur lors de la mise à jour du statut'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _updating = false);
    }
  }

  Future<void> _assignAgent(String agentId) async {
    setState(() => _updating = true);
    try {
      await ApiClient().dio.put(
        '${ApiConstants.tickets}${widget.ticketId}/assign',
        data: {'agent_id': agentId},
      );
      await _fetchTicket();
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Agent assigné avec succès')),
        );
      }
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Erreur lors de l\'assignation de l\'agent'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    } finally {
      if (mounted) setState(() => _updating = false);
    }
  }

  void _showStatusDialog() {
    final statuses = [
      {'label': 'OUVERT', 'value': 'OPEN'},
      {'label': 'EN COURS', 'value': 'IN_PROGRESS'},
      {'label': 'RÉSOLU', 'value': 'RESOLVED'},
      {'label': 'FERMÉ', 'value': 'CLOSED'},
    ];

    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.surfaceElevated,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Modifier le statut',
                style: TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              ...statuses.map((s) => ListTile(
                    title: Text(
                      s['label']!,
                      style: const TextStyle(color: AppTheme.textPrimary),
                    ),
                    onTap: () {
                      Navigator.pop(ctx);
                      _updateStatus(s['value']!);
                    },
                  )),
            ],
          ),
        ),
      ),
    );
  }

  void _showAssignDialog() {
    showModalBottomSheet(
      context: context,
      backgroundColor: AppTheme.surfaceElevated,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
      ),
      builder: (ctx) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                'Assigner un agent',
                style: TextStyle(
                  color: AppTheme.textPrimary,
                  fontSize: 16,
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 16),
              if (_agents.isEmpty)
                const Padding(
                  padding: EdgeInsets.all(16.0),
                  child: Text(
                    'Aucun agent disponible',
                    style: TextStyle(color: AppTheme.textMuted),
                  ),
                )
              else
                ..._agents.map((ag) {
                  final id = ag['id'] as String? ?? '';
                  final shortId = id.length >= 6 ? id.substring(id.length - 6).toUpperCase() : id;
                  return ListTile(
                    leading: const Icon(Icons.person_outline, color: AppTheme.primaryLight),
                    title: Text('Agent #$shortId', style: const TextStyle(color: AppTheme.textPrimary)),
                    subtitle: Text(
                      ((ag['skills'] as List<dynamic>?) ?? []).join(', '),
                      style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                    ),
                    onTap: () {
                      Navigator.pop(ctx);
                      _assignAgent(id);
                    },
                  );
                }),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = context.read<AuthProvider>().currentUser;
    final canManage = user?.role == 'ADMIN' || user?.role == 'AGENT';

    return Scaffold(
      appBar: AppBar(
        title: const Text('Détail du Ticket'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded),
            onPressed: _fetchTicket,
          ),
        ],
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      const Icon(Icons.error_outline, color: AppTheme.error, size: 48),
                      const SizedBox(height: 12),
                      Text(_error!, style: const TextStyle(color: AppTheme.textSecondary)),
                      const SizedBox(height: 16),
                      ElevatedButton(
                        onPressed: _fetchTicket,
                        child: const Text('Réessayer'),
                      ),
                    ],
                  ),
                )
              : _ticket == null
                  ? const Center(child: Text('Ticket non trouvé', style: TextStyle(color: AppTheme.textSecondary)))
                  : SingleChildScrollView(
                      padding: const EdgeInsets.all(16),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          _buildHeaderCard(),
                          const SizedBox(height: 16),
                          _buildDetailsCard(),
                          const SizedBox(height: 16),
                          if (_ticket!['resolution_note'] != null &&
                              (_ticket!['resolution_note'] as String).isNotEmpty) ...[
                            _buildResolutionCard(),
                            const SizedBox(height: 16),
                          ],
                          if (canManage) _buildActionsCard(),
                        ],
                      ),
                    ),
    );
  }

  Widget _buildHeaderCard() {
    final status = (_ticket!['status'] as String? ?? 'OPEN').toUpperCase();
    final priority = (_ticket!['priority'] as String? ?? 'LOW').toUpperCase();

    Color statusColor;
    switch (status) {
      case 'OPEN':
        statusColor = AppTheme.info;
        break;
      case 'IN_PROGRESS':
        statusColor = AppTheme.warning;
        break;
      case 'RESOLVED':
        statusColor = AppTheme.success;
        break;
      default:
        statusColor = AppTheme.textMuted;
    }

    Color priorityColor;
    switch (priority) {
      case 'CRITICAL':
      case 'HIGH':
        priorityColor = AppTheme.error;
        break;
      case 'MEDIUM':
        priorityColor = AppTheme.warning;
        break;
      default:
        priorityColor = AppTheme.accentLight;
    }

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1F293D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: statusColor.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: statusColor.withValues(alpha: 0.4)),
                ),
                child: Text(
                  status.replaceAll('_', ' '),
                  style: TextStyle(
                    color: statusColor,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                decoration: BoxDecoration(
                  color: priorityColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  priority,
                  style: TextStyle(
                    color: priorityColor,
                    fontSize: 11,
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            _ticket!['subject'] as String? ?? 'Sans sujet',
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDetailsCard() {
    final cat = _ticket!['category'] as String? ?? 'Général';
    final desc = _ticket!['description'] as String? ?? '';
    final createdAt = _ticket!['created_at'] as String?;
    String dateStr = 'Inconnue';
    if (createdAt != null) {
      try {
        dateStr = DateFormat('dd/MM/yyyy à HH:mm').format(DateTime.parse(createdAt));
      } catch (_) {}
    }

    final assignedTo = _ticket!['assigned_agent_id'] as String?;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1F293D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'DESCRIPTION',
            style: TextStyle(
              color: AppTheme.textSecondary,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 8),
          Text(
            desc,
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 14,
              height: 1.4,
            ),
          ),
          const Divider(height: 24, color: Color(0xFF1F293D)),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Catégorie', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
              Text(cat, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Date de création', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
              Text(dateStr, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.w600)),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text('Agent assigné', style: TextStyle(color: AppTheme.textSecondary, fontSize: 13)),
              Text(
                assignedTo != null && assignedTo.isNotEmpty
                    ? '#${assignedTo.length >= 6 ? assignedTo.substring(assignedTo.length - 6).toUpperCase() : assignedTo}'
                    : 'Non assigné',
                style: TextStyle(
                  color: assignedTo != null ? AppTheme.primaryLight : AppTheme.textMuted,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildResolutionCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.success.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.success.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            children: [
              Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 18),
              SizedBox(width: 8),
              Text(
                'Note de résolution',
                style: TextStyle(
                  color: AppTheme.success,
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            _ticket!['resolution_note'] as String,
            style: const TextStyle(
              color: AppTheme.textPrimary,
              fontSize: 13,
              height: 1.4,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildActionsCard() {
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1F293D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Text(
            'ACTIONS SUPPORT',
            style: TextStyle(
              color: AppTheme.textSecondary,
              fontSize: 12,
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _updating ? null : _showStatusDialog,
                  icon: const Icon(Icons.sync_alt_rounded, size: 16),
                  label: const Text('Changer Statut'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.primaryLight,
                    side: const BorderSide(color: Color(0xFF27354A)),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: _updating ? null : _showAssignDialog,
                  icon: const Icon(Icons.person_add_alt_1_rounded, size: 16),
                  label: const Text('Assigner'),
                  style: OutlinedButton.styleFrom(
                    foregroundColor: AppTheme.primaryLight,
                    side: const BorderSide(color: Color(0xFF27354A)),
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
