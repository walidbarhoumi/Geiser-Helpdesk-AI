import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../core/theme/app_theme.dart';
import '../../core/constants/api_constants.dart';
import '../../data/services/api_client.dart';
import '../providers/auth_provider.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  bool _loading = true;
  String? _error;
  Map<String, dynamic>? _kpis;
  List<dynamic> _recentTickets = [];

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    final dio = ApiClient().dio;
    final role = context.read<AuthProvider>().currentUser?.role ?? 'USER';
    try {
      if (role == 'ADMIN' || role == 'AGENT') {
        final res = await dio.get(ApiConstants.analyticsDB);
        _kpis = res.data['kpis'] as Map<String, dynamic>?;
      }
      final ticketsRes = await dio.get(ApiConstants.tickets,
          queryParameters: {'limit': 5, 'skip': 0});
      final raw = ticketsRes.data;
      _recentTickets = raw is List ? raw : [];
    } catch (e) {
      _error = 'Impossible de charger les données';
    }
    if (mounted) setState(() => _loading = false);
  }

  @override
  Widget build(BuildContext context) {
    final user = context.read<AuthProvider>().currentUser;
    final isAdminOrAgent =
        user?.role == 'ADMIN' || user?.role == 'AGENT';

    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _fetch,
          color: AppTheme.primaryLight,
          backgroundColor: AppTheme.surfaceElevated,
          child: CustomScrollView(
            slivers: [
              // ── Header ──────────────────────────────────────
              SliverToBoxAdapter(
                child: Padding(
                  padding: const EdgeInsets.fromLTRB(16, 16, 16, 0),
                  child: Container(
                    decoration: BoxDecoration(
                      gradient: AppTheme.primaryGradient,
                      borderRadius: BorderRadius.circular(20),
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.primary.withValues(alpha: 0.35),
                          blurRadius: 24,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    padding: const EdgeInsets.all(20),
                    child: Row(
                      children: [
                        const Icon(Icons.bar_chart_rounded,
                            color: Colors.white, size: 28),
                        const SizedBox(width: 12),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              const Text(
                                'Tableau de Bord',
                                style: TextStyle(
                                  color: Colors.white,
                                  fontSize: 20,
                                  fontWeight: FontWeight.w800,
                                  letterSpacing: -0.3,
                                ),
                              ),
                              Text(
                                isAdminOrAgent
                                    ? 'Vue consolidée des métriques ITSM'
                                    : 'Aperçu de vos demandes',
                                style: TextStyle(
                                  color:
                                      Colors.white.withValues(alpha: 0.75),
                                  fontSize: 12,
                                ),
                              ),
                            ],
                          ),
                        ),
                        IconButton(
                          icon: const Icon(Icons.refresh_rounded,
                              color: Colors.white, size: 22),
                          onPressed: _fetch,
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              if (_loading)
                const SliverFillRemaining(
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_error != null)
                SliverFillRemaining(
                  child: Center(
                    child: Column(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        const Icon(Icons.error_outline,
                            color: AppTheme.error, size: 48),
                        const SizedBox(height: 12),
                        Text(_error!,
                            style: const TextStyle(
                                color: AppTheme.textSecondary,
                                fontSize: 14)),
                        const SizedBox(height: 16),
                        ElevatedButton.icon(
                          onPressed: _fetch,
                          icon: const Icon(Icons.refresh_rounded, size: 18),
                          label: const Text('Réessayer'),
                        ),
                      ],
                    ),
                  ),
                )
              else ...[
                // ── KPI Grid ──────────────────────────────────
                if (isAdminOrAgent && _kpis != null)
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(16, 20, 16, 0),
                    sliver: SliverGrid(
                      gridDelegate:
                          const SliverGridDelegateWithFixedCrossAxisCount(
                        crossAxisCount: 2,
                        mainAxisSpacing: 12,
                        crossAxisSpacing: 12,
                        childAspectRatio: 1.4,
                      ),
                      delegate: SliverChildListDelegate([
                        _KpiCard(
                          label: 'Total Tickets',
                          value: '${_kpis!['total_tickets'] ?? 0}',
                          icon: Icons.confirmation_number_rounded,
                          color: AppTheme.primary,
                        ),
                        _KpiCard(
                          label: 'Ouverts',
                          value: '${_kpis!['open_tickets'] ?? 0}',
                          icon: Icons.inbox_rounded,
                          color: AppTheme.info,
                        ),
                        _KpiCard(
                          label: 'En Cours',
                          value:
                              '${_kpis!['in_progress_tickets'] ?? 0}',
                          icon: Icons.hourglass_top_rounded,
                          color: AppTheme.warning,
                        ),
                        _KpiCard(
                          label: 'Résolus',
                          value:
                              '${_kpis!['resolved_tickets'] ?? 0}',
                          icon: Icons.check_circle_rounded,
                          color: AppTheme.success,
                        ),
                        _KpiCard(
                          label: 'SLA Respecté',
                          value:
                              '${(_kpis!['overall_sla_compliance_pct'] ?? 0).toStringAsFixed(0)}%',
                          icon: Icons.shield_rounded,
                          color: const Color(0xFF8B5CF6),
                        ),
                        _KpiCard(
                          label: 'CSAT Moyen',
                          value: _kpis!['satisfaction_avg'] != null
                              ? '${(_kpis!['satisfaction_avg'] as num).toStringAsFixed(1)}/5'
                              : 'N/D',
                          icon: Icons.star_rounded,
                          color: const Color(0xFFF59E0B),
                        ),
                      ]),
                    ),
                  ),

                // ── Recent Tickets ─────────────────────────────
                SliverToBoxAdapter(
                  child: Padding(
                    padding:
                        const EdgeInsets.fromLTRB(16, 24, 16, 8),
                    child: Row(
                      children: [
                        const Icon(Icons.history_rounded,
                            color: AppTheme.primaryLight, size: 18),
                        const SizedBox(width: 8),
                        const Text(
                          'Activité Récente',
                          style: TextStyle(
                            color: AppTheme.textPrimary,
                            fontSize: 15,
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        const Spacer(),
                        Text(
                          '${_recentTickets.length} ticket(s)',
                          style: const TextStyle(
                              color: AppTheme.textMuted, fontSize: 12),
                        ),
                      ],
                    ),
                  ),
                ),

                if (_recentTickets.isEmpty)
                  const SliverToBoxAdapter(
                    child: Padding(
                      padding: EdgeInsets.all(32),
                      child: Center(
                        child: Text(
                          'Aucun ticket pour l\'instant',
                          style: TextStyle(
                              color: AppTheme.textMuted, fontSize: 13),
                        ),
                      ),
                    ),
                  )
                else
                  SliverPadding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                    sliver: SliverList(
                      delegate: SliverChildBuilderDelegate(
                        (context, i) {
                          final t = _recentTickets[i]
                              as Map<String, dynamic>;
                          return _RecentTicketCard(ticket: t);
                        },
                        childCount: _recentTickets.length,
                      ),
                    ),
                  ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _KpiCard extends StatelessWidget {
  final String label;
  final String value;
  final IconData icon;
  final Color color;

  const _KpiCard({
    required this.label,
    required this.value,
    required this.icon,
    required this.color,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1F293D)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.2),
            blurRadius: 10,
            offset: const Offset(0, 4),
          ),
        ],
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Container(
            width: 34,
            height: 34,
            decoration: BoxDecoration(
              color: color.withValues(alpha: 0.15),
              borderRadius: BorderRadius.circular(10),
            ),
            child: Icon(icon, color: color, size: 18),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                value,
                style: TextStyle(
                  color: color,
                  fontSize: 22,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.5,
                ),
              ),
              const SizedBox(height: 2),
              Text(
                label,
                style: const TextStyle(
                  color: AppTheme.textSecondary,
                  fontSize: 11,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RecentTicketCard extends StatelessWidget {
  final Map<String, dynamic> ticket;

  const _RecentTicketCard({required this.ticket});

  @override
  Widget build(BuildContext context) {
    final status = (ticket['status'] as String? ?? 'OPEN').toUpperCase();
    final priority =
        (ticket['priority'] as String? ?? 'LOW').toUpperCase();
    final subject =
        ticket['subject'] as String? ?? 'Sans titre';
    final createdAt = ticket['created_at'] as String?;
    String dateStr = '';
    if (createdAt != null) {
      try {
        dateStr = DateFormat('dd/MM HH:mm')
            .format(DateTime.parse(createdAt));
      } catch (_) {}
    }

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
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFF1F293D)),
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
      child: Row(
        children: [
          Container(
            width: 8,
            height: 8,
            decoration: BoxDecoration(
              color: statusColor,
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  subject,
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                  style: const TextStyle(
                    color: AppTheme.textPrimary,
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                  ),
                ),
                const SizedBox(height: 4),
                Row(
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 6, vertical: 2),
                      decoration: BoxDecoration(
                        color: priorityColor.withValues(alpha: 0.12),
                        borderRadius: BorderRadius.circular(4),
                      ),
                      child: Text(
                        priority,
                        style: TextStyle(
                            color: priorityColor,
                            fontSize: 10,
                            fontWeight: FontWeight.bold),
                      ),
                    ),
                    const SizedBox(width: 6),
                    Text(
                      status.replaceAll('_', ' '),
                      style: TextStyle(
                          color: statusColor,
                          fontSize: 10,
                          fontWeight: FontWeight.w600),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Text(
            dateStr,
            style: const TextStyle(
                color: AppTheme.textMuted, fontSize: 10),
          ),
        ],
      ),
    );
  }
}
