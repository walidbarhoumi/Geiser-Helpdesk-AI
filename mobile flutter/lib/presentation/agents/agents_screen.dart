import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../core/constants/api_constants.dart';
import '../../data/services/api_client.dart';
import '../providers/auth_provider.dart';

class AgentsScreen extends StatefulWidget {
  const AgentsScreen({super.key});

  @override
  State<AgentsScreen> createState() => _AgentsScreenState();
}

class _AgentsScreenState extends State<AgentsScreen> {
  bool _loading = true;
  String? _error;
  List<dynamic> _agents = [];
  String _search = '';
  String _filter = 'all'; // all | available | busy

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
    try {
      final res = await ApiClient().dio.get(ApiConstants.agents);
      _agents = res.data is List ? res.data as List<dynamic> : [];
    } catch (_) {
      _error = 'Impossible de charger les agents';
    }
    if (mounted) setState(() => _loading = false);
  }

  List<dynamic> get _filtered {
    return _agents.where((a) {
      final skills = (a['skills'] as List<dynamic>? ?? [])
          .map((s) => s.toString().toLowerCase())
          .toList();
      final id = (a['id'] as String? ?? '').toLowerCase();
      final q = _search.toLowerCase();
      final matchSearch = q.isEmpty ||
          id.contains(q) ||
          skills.any((s) => s.contains(q));
      final avail = a['is_available'] as bool? ?? false;
      final matchFilter = _filter == 'all' ||
          (_filter == 'available' && avail) ||
          (_filter == 'busy' && !avail);
      return matchSearch && matchFilter;
    }).toList();
  }

  Future<void> _toggleAvailability(String id, bool current) async {
    try {
      await ApiClient().dio.put(
        '/agents/$id',
        data: {'is_available': !current},
      );
      _fetch();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Erreur lors de la mise à jour')),
        );
      }
    }
  }

  Future<void> _deleteAgent(String id) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surfaceElevated,
        title: const Text('Supprimer l\'agent',
            style: TextStyle(color: AppTheme.textPrimary)),
        content: const Text('Cette action est irréversible.',
            style: TextStyle(color: AppTheme.textSecondary)),
        actions: [
          TextButton(
              onPressed: () => Navigator.pop(ctx, false),
              child: const Text('Annuler')),
          TextButton(
              onPressed: () => Navigator.pop(ctx, true),
              child: const Text('Supprimer',
                  style: TextStyle(color: AppTheme.error))),
        ],
      ),
    );
    if (confirm == true) {
      try {
        await ApiClient().dio.delete('/agents/$id');
        _fetch();
      } catch (_) {
        if (mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(content: Text('Erreur lors de la suppression')),
          );
        }
      }
    }
  }

  void _openEditSheet(Map<String, dynamic> agent) {
    final skillsController = TextEditingController(
      text: (agent['skills'] as List<dynamic>? ?? []).join(', '),
    );
    bool avail = agent['is_available'] as bool? ?? false;

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surfaceElevated,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) {
        return StatefulBuilder(
          builder: (ctx, setModal) {
            return Padding(
              padding: EdgeInsets.fromLTRB(
                  20, 20, 20, MediaQuery.of(ctx).viewInsets.bottom + 20),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(children: [
                    Container(
                      width: 4,
                      height: 20,
                      decoration: BoxDecoration(
                        gradient: AppTheme.primaryGradient,
                        borderRadius: BorderRadius.circular(2),
                      ),
                    ),
                    const SizedBox(width: 10),
                    const Text('Modifier l\'agent',
                        style: TextStyle(
                            color: AppTheme.textPrimary,
                            fontSize: 16,
                            fontWeight: FontWeight.bold)),
                    const Spacer(),
                    IconButton(
                      icon: const Icon(Icons.close, color: AppTheme.textMuted),
                      onPressed: () => Navigator.pop(ctx),
                    ),
                  ]),
                  const SizedBox(height: 16),
                  TextField(
                    controller: skillsController,
                    style: const TextStyle(color: AppTheme.textPrimary),
                    decoration: const InputDecoration(
                      labelText: 'Compétences (séparées par virgules)',
                      prefixIcon: Icon(Icons.psychology_rounded,
                          color: AppTheme.primaryLight, size: 20),
                    ),
                  ),
                  const SizedBox(height: 16),
                  GestureDetector(
                    onTap: () => setModal(() => avail = !avail),
                    child: Container(
                      padding: const EdgeInsets.symmetric(
                          horizontal: 14, vertical: 12),
                      decoration: BoxDecoration(
                        color: avail
                            ? AppTheme.success.withValues(alpha: 0.1)
                            : AppTheme.surface,
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(
                          color: avail
                              ? AppTheme.success.withValues(alpha: 0.4)
                              : const Color(0xFF1F293D),
                        ),
                      ),
                      child: Row(
                        children: [
                          Icon(
                            avail
                                ? Icons.circle
                                : Icons.circle_outlined,
                            color: avail
                                ? AppTheme.success
                                : AppTheme.textMuted,
                            size: 14,
                          ),
                          const SizedBox(width: 10),
                          Text(
                            avail ? 'Disponible' : 'Indisponible',
                            style: TextStyle(
                              color: avail
                                  ? AppTheme.success
                                  : AppTheme.textSecondary,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          const Spacer(),
                          Switch(
                            value: avail,
                            onChanged: (v) => setModal(() => avail = v),
                            activeThumbColor: AppTheme.success,
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 20),
                  Container(
                    width: double.infinity,
                    height: 48,
                    decoration: BoxDecoration(
                      gradient: AppTheme.primaryGradient,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.transparent,
                        shadowColor: Colors.transparent,
                        shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(12)),
                      ),
                      onPressed: () async {
                        try {
                          final skills = skillsController.text
                              .split(',')
                              .map((s) => s.trim())
                              .where((s) => s.isNotEmpty)
                              .toList();
                          await ApiClient().dio.put(
                            '/agents/${agent['id']}',
                            data: {
                              'skills': skills,
                              'is_available': avail,
                            },
                          );
                          if (ctx.mounted) Navigator.pop(ctx);
                          _fetch();
                        } catch (_) {
                          if (ctx.mounted) {
                            ScaffoldMessenger.of(ctx).showSnackBar(
                              const SnackBar(
                                  content: Text('Erreur lors de la mise à jour')),
                            );
                          }
                        }
                      },
                      child: const Text('Enregistrer',
                          style: TextStyle(
                              color: Colors.white,
                              fontWeight: FontWeight.bold,
                              fontSize: 15)),
                    ),
                  ),
                ],
              ),
            );
          },
        );
      },
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = context.read<AuthProvider>().currentUser;
    final isAdmin = user?.role == 'ADMIN';
    final filtered = _filtered;

    return Scaffold(
      appBar: AppBar(
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Gestion des Agents',
                style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
            Text('Équipe de support',
                style:
                    TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, size: 22),
            onPressed: _fetch,
          ),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          // Search + filter
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: TextField(
              onChanged: (v) => setState(() => _search = v),
              style: const TextStyle(color: AppTheme.textPrimary),
              decoration: const InputDecoration(
                hintText: 'Rechercher par ID ou compétence...',
                prefixIcon: Icon(Icons.search_rounded,
                    color: AppTheme.textSecondary, size: 20),
                contentPadding:
                    EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
            ),
          ),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            child: Row(
              children: [
                _FilterChip(
                    label: 'Tous',
                    value: 'all',
                    selected: _filter == 'all',
                    onTap: () => setState(() => _filter = 'all')),
                const SizedBox(width: 8),
                _FilterChip(
                    label: 'Disponibles',
                    value: 'available',
                    selected: _filter == 'available',
                    onTap: () => setState(() => _filter = 'available')),
                const SizedBox(width: 8),
                _FilterChip(
                    label: 'Occupés',
                    value: 'busy',
                    selected: _filter == 'busy',
                    onTap: () => setState(() => _filter = 'busy')),
                const SizedBox(width: 16),
                Text(
                  '${filtered.length} agent(s)',
                  style: const TextStyle(
                      color: AppTheme.textMuted, fontSize: 12),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),

          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            const Icon(Icons.error_outline,
                                color: AppTheme.error, size: 40),
                            const SizedBox(height: 12),
                            Text(_error!,
                                style: const TextStyle(
                                    color: AppTheme.textSecondary)),
                            const SizedBox(height: 12),
                            ElevatedButton(
                                onPressed: _fetch,
                                child: const Text('Réessayer')),
                          ],
                        ),
                      )
                    : filtered.isEmpty
                        ? const Center(
                            child: Column(
                              mainAxisAlignment: MainAxisAlignment.center,
                              children: [
                                Icon(Icons.group_off_rounded,
                                    color: AppTheme.textMuted, size: 48),
                                SizedBox(height: 12),
                                Text('Aucun agent trouvé',
                                    style: TextStyle(
                                        color: AppTheme.textSecondary,
                                        fontSize: 14)),
                              ],
                            ),
                          )
                        : RefreshIndicator(
                            onRefresh: _fetch,
                            color: AppTheme.primaryLight,
                            child: ListView.builder(
                              padding: const EdgeInsets.fromLTRB(
                                  16, 0, 16, 24),
                              itemCount: filtered.length,
                              itemBuilder: (context, i) {
                                final agent =
                                    filtered[i] as Map<String, dynamic>;
                                return _AgentCard(
                                  agent: agent,
                                  isAdmin: isAdmin,
                                  onEdit: () => _openEditSheet(agent),
                                  onDelete: () =>
                                      _deleteAgent(agent['id'] as String),
                                  onToggle: () => _toggleAvailability(
                                    agent['id'] as String,
                                    agent['is_available'] as bool? ?? false,
                                  ),
                                );
                              },
                            ),
                          ),
          ),
        ],
      ),
    );
  }
}

class _FilterChip extends StatelessWidget {
  final String label;
  final String value;
  final bool selected;
  final VoidCallback onTap;

  const _FilterChip({
    required this.label,
    required this.value,
    required this.selected,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding:
            const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        decoration: BoxDecoration(
          color: selected ? AppTheme.primary : AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: selected
                ? AppTheme.primaryLight
                : const Color(0xFF27354A),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight:
                selected ? FontWeight.bold : FontWeight.w500,
            color: selected
                ? Colors.white
                : AppTheme.textSecondary,
          ),
        ),
      ),
    );
  }
}

class _AgentCard extends StatelessWidget {
  final Map<String, dynamic> agent;
  final bool isAdmin;
  final VoidCallback onEdit;
  final VoidCallback onDelete;
  final VoidCallback onToggle;

  const _AgentCard({
    required this.agent,
    required this.isAdmin,
    required this.onEdit,
    required this.onDelete,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final id = agent['id'] as String? ?? '';
    final shortId = id.length >= 6 ? id.substring(id.length - 6).toUpperCase() : id.toUpperCase();
    final initials = id.length >= 2 ? id.substring(id.length - 2).toUpperCase() : '??';
    final hue = id.isNotEmpty
        ? (int.tryParse(id.substring(id.length > 3 ? id.length - 3 : 0), radix: 16) ?? 0) % 360
        : 240;
    final isAvail = agent['is_available'] as bool? ?? false;
    final workload = (agent['workload'] as num? ?? 0).toInt();
    final skills = (agent['skills'] as List<dynamic>? ?? [])
        .map((s) => s.toString())
        .toList();

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF1F293D)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.15),
            blurRadius: 8,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      padding: const EdgeInsets.all(14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // Avatar
              Stack(
                children: [
                  Container(
                    width: 46,
                    height: 46,
                    decoration: BoxDecoration(
                      color: HSLColor.fromAHSL(1.0, hue.toDouble(), 0.6, 0.15).toColor(),
                      borderRadius: BorderRadius.circular(14),
                      border: Border.all(
                        color: HSLColor.fromAHSL(0.4, hue.toDouble(), 0.6, 0.35).toColor(),
                      ),
                    ),
                    child: Center(
                      child: Text(
                        initials,
                        style: TextStyle(
                          color: HSLColor.fromAHSL(1.0, hue.toDouble(), 0.7, 0.7).toColor(),
                          fontWeight: FontWeight.bold,
                          fontSize: 15,
                        ),
                      ),
                    ),
                  ),
                  Positioned(
                    bottom: 0,
                    right: 0,
                    child: Container(
                      width: 12,
                      height: 12,
                      decoration: BoxDecoration(
                        color: isAvail ? AppTheme.success : AppTheme.textMuted,
                        shape: BoxShape.circle,
                        border: Border.all(
                            color: AppTheme.surface, width: 2),
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Agent #$shortId',
                      style: const TextStyle(
                        color: AppTheme.textPrimary,
                        fontWeight: FontWeight.w700,
                        fontSize: 14,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Text(
                      isAvail ? '● Disponible' : '● Hors ligne',
                      style: TextStyle(
                        color: isAvail
                            ? AppTheme.success
                            : AppTheme.textMuted,
                        fontSize: 11,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
              if (isAdmin) ...[
                IconButton(
                  icon: const Icon(Icons.edit_rounded,
                      color: AppTheme.primaryLight, size: 18),
                  onPressed: onEdit,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                      minWidth: 32, minHeight: 32),
                ),
                IconButton(
                  icon: const Icon(Icons.delete_outline_rounded,
                      color: AppTheme.error, size: 18),
                  onPressed: onDelete,
                  padding: EdgeInsets.zero,
                  constraints: const BoxConstraints(
                      minWidth: 32, minHeight: 32),
                ),
              ],
            ],
          ),
          const SizedBox(height: 12),

          // Skills
          if (skills.isNotEmpty)
            Wrap(
              spacing: 6,
              runSpacing: 4,
              children: skills.take(4).map((s) {
                return Container(
                  padding: const EdgeInsets.symmetric(
                      horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppTheme.primary.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(
                        color: AppTheme.primary.withValues(alpha: 0.2)),
                  ),
                  child: Text(
                    s,
                    style: const TextStyle(
                      color: AppTheme.primaryLight,
                      fontSize: 11,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                );
              }).toList(),
            ),

          const SizedBox(height: 10),

          // Workload bar
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  const Text('Charge',
                      style: TextStyle(
                          color: AppTheme.textMuted, fontSize: 11)),
                  Text('$workload%',
                      style: TextStyle(
                        color: workload > 75
                            ? AppTheme.error
                            : AppTheme.textSecondary,
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                      )),
                ],
              ),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: LinearProgressIndicator(
                  value: workload / 100,
                  backgroundColor:
                      AppTheme.surfaceElevated,
                  color: workload > 75
                      ? AppTheme.error
                      : workload > 50
                          ? AppTheme.warning
                          : AppTheme.success,
                  minHeight: 5,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
