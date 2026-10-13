import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../core/constants/api_constants.dart';
import '../../data/services/api_client.dart';
import '../providers/auth_provider.dart';

class TeamsScreen extends StatefulWidget {
  const TeamsScreen({super.key});

  @override
  State<TeamsScreen> createState() => _TeamsScreenState();
}

class _TeamsScreenState extends State<TeamsScreen> {
  bool _loading = true;
  String? _error;
  List<dynamic> _teams = [];
  final Set<String> _expanded = {};

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() { _loading = true; _error = null; });
    try {
      final res = await ApiClient().dio.get(ApiConstants.teams);
      _teams = res.data is List ? res.data as List<dynamic> : [];
    } catch (_) {
      _error = 'Impossible de charger les équipes';
    }
    if (mounted) setState(() => _loading = false);
  }

  void _showCreateSheet() {
    final nameCtrl = TextEditingController();
    final descCtrl = TextEditingController();
    final specCtrl = TextEditingController();

    showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: AppTheme.surfaceElevated,
      shape: const RoundedRectangleBorder(
        borderRadius: BorderRadius.vertical(top: Radius.circular(24)),
      ),
      builder: (ctx) => Padding(
        padding: EdgeInsets.fromLTRB(20, 20, 20, MediaQuery.of(ctx).viewInsets.bottom + 20),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(children: [
              Container(width: 4, height: 20, decoration: BoxDecoration(gradient: AppTheme.primaryGradient, borderRadius: BorderRadius.circular(2))),
              const SizedBox(width: 10),
              const Text('Nouvelle Équipe', style: TextStyle(color: AppTheme.textPrimary, fontSize: 16, fontWeight: FontWeight.bold)),
              const Spacer(),
              IconButton(icon: const Icon(Icons.close, color: AppTheme.textMuted), onPressed: () => Navigator.pop(ctx)),
            ]),
            const SizedBox(height: 16),
            TextField(controller: nameCtrl, style: const TextStyle(color: AppTheme.textPrimary),
              decoration: const InputDecoration(labelText: 'Nom de l\'équipe *',
                prefixIcon: Icon(Icons.group_rounded, color: AppTheme.primaryLight, size: 20))),
            const SizedBox(height: 12),
            TextField(controller: descCtrl, style: const TextStyle(color: AppTheme.textPrimary), maxLines: 2,
              decoration: const InputDecoration(labelText: 'Description',
                prefixIcon: Icon(Icons.description_rounded, color: AppTheme.primaryLight, size: 20))),
            const SizedBox(height: 12),
            TextField(controller: specCtrl, style: const TextStyle(color: AppTheme.textPrimary),
              decoration: const InputDecoration(labelText: 'Spécialisation',
                prefixIcon: Icon(Icons.star_rounded, color: AppTheme.primaryLight, size: 20))),
            const SizedBox(height: 20),
            Container(
              width: double.infinity, height: 48,
              decoration: BoxDecoration(gradient: AppTheme.primaryGradient, borderRadius: BorderRadius.circular(12)),
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(backgroundColor: Colors.transparent, shadowColor: Colors.transparent,
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
                onPressed: () async {
                  if (nameCtrl.text.trim().isEmpty) return;
                  try {
                    await ApiClient().dio.post(ApiConstants.teams, data: {
                      'name': nameCtrl.text.trim(),
                      'description': descCtrl.text.trim(),
                      'specialization': specCtrl.text.trim(),
                    });
                    if (ctx.mounted) Navigator.pop(ctx);
                    _fetch();
                  } catch (_) {
                    if (ctx.mounted) {
                      ScaffoldMessenger.of(ctx).showSnackBar(
                        const SnackBar(content: Text('Erreur lors de la création')),
                      );
                    }
                  }
                },
                child: const Text('Créer l\'équipe', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 15)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final user = context.read<AuthProvider>().currentUser;
    final isAdmin = user?.role == 'ADMIN';

    return Scaffold(
      appBar: AppBar(
        title: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Équipes', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
          Text('Gestion des équipes de support', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        ]),
        actions: [
          IconButton(icon: const Icon(Icons.refresh_rounded, size: 22), onPressed: _fetch),
          const SizedBox(width: 8),
        ],
      ),
      floatingActionButton: isAdmin
          ? Container(
              decoration: BoxDecoration(gradient: AppTheme.primaryGradient, borderRadius: BorderRadius.circular(16),
                boxShadow: [BoxShadow(color: AppTheme.primary.withValues(alpha: 0.35), blurRadius: 16, offset: const Offset(0, 6))]),
              child: FloatingActionButton(
                backgroundColor: Colors.transparent, elevation: 0,
                onPressed: _showCreateSheet,
                child: const Icon(Icons.add_rounded, color: Colors.white, size: 26),
              ),
            )
          : null,
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : _error != null
              ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                  const Icon(Icons.error_outline, color: AppTheme.error, size: 40),
                  const SizedBox(height: 12),
                  Text(_error!, style: const TextStyle(color: AppTheme.textSecondary)),
                  const SizedBox(height: 12),
                  ElevatedButton(onPressed: _fetch, child: const Text('Réessayer')),
                ]))
              : _teams.isEmpty
                  ? const Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                      Icon(Icons.groups_rounded, color: AppTheme.textMuted, size: 56),
                      SizedBox(height: 12),
                      Text('Aucune équipe créée', style: TextStyle(color: AppTheme.textSecondary, fontSize: 14)),
                    ]))
                  : RefreshIndicator(
                      onRefresh: _fetch, color: AppTheme.primaryLight,
                      child: ListView.builder(
                        padding: const EdgeInsets.fromLTRB(16, 12, 16, 100),
                        itemCount: _teams.length,
                        itemBuilder: (context, i) {
                          final team = _teams[i] as Map<String, dynamic>;
                          final id = team['id'] as String? ?? '';
                          final isExp = _expanded.contains(id);
                          final agents = (team['agent_ids'] as List<dynamic>? ?? []);
                          final isActive = team['is_active'] as bool? ?? true;

                          return Container(
                            margin: const EdgeInsets.only(bottom: 14),
                            decoration: BoxDecoration(
                              color: AppTheme.surface,
                              borderRadius: BorderRadius.circular(18),
                              border: Border.all(color: const Color(0xFF1F293D)),
                              boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.18), blurRadius: 10, offset: const Offset(0, 4))],
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                // Header gradient
                                Container(
                                  width: double.infinity,
                                  padding: const EdgeInsets.fromLTRB(16, 14, 16, 12),
                                  decoration: BoxDecoration(
                                    gradient: LinearGradient(
                                      colors: [AppTheme.primary.withValues(alpha: 0.18), AppTheme.primary.withValues(alpha: 0.06)],
                                      begin: Alignment.topLeft, end: Alignment.bottomRight,
                                    ),
                                    borderRadius: const BorderRadius.vertical(top: Radius.circular(18)),
                                    border: const Border(bottom: BorderSide(color: Color(0xFF1F293D))),
                                  ),
                                  child: Row(children: [
                                    Container(
                                      width: 38, height: 38,
                                      decoration: BoxDecoration(gradient: AppTheme.primaryGradient, borderRadius: BorderRadius.circular(10)),
                                      child: const Icon(Icons.group_rounded, color: Colors.white, size: 20),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                      Text(team['name'] as String? ?? 'Équipe', style: const TextStyle(color: AppTheme.textPrimary, fontSize: 15, fontWeight: FontWeight.bold)),
                                      if ((team['specialization'] as String? ?? '').isNotEmpty)
                                        Text(team['specialization'] as String, style: const TextStyle(color: AppTheme.primaryLight, fontSize: 11, fontWeight: FontWeight.w600)),
                                    ])),
                                    Container(
                                      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                                      decoration: BoxDecoration(
                                        color: isActive ? AppTheme.success.withValues(alpha: 0.12) : AppTheme.textMuted.withValues(alpha: 0.12),
                                        borderRadius: BorderRadius.circular(20),
                                        border: Border.all(color: isActive ? AppTheme.success.withValues(alpha: 0.3) : AppTheme.textMuted.withValues(alpha: 0.3)),
                                      ),
                                      child: Text(isActive ? 'Active' : 'Inactive',
                                        style: TextStyle(color: isActive ? AppTheme.success : AppTheme.textMuted, fontSize: 11, fontWeight: FontWeight.bold)),
                                    ),
                                  ]),
                                ),

                                Padding(
                                  padding: const EdgeInsets.all(14),
                                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                    if ((team['description'] as String? ?? '').isNotEmpty)
                                      Padding(
                                        padding: const EdgeInsets.only(bottom: 10),
                                        child: Text(team['description'] as String,
                                          style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13, height: 1.4)),
                                      ),

                                    Row(children: [
                                      const Icon(Icons.person_rounded, color: AppTheme.primaryLight, size: 14),
                                      const SizedBox(width: 4),
                                      Text('${agents.length} membre(s)',
                                        style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12, fontWeight: FontWeight.w600)),
                                      const Spacer(),
                                      if (agents.isNotEmpty)
                                        GestureDetector(
                                          onTap: () => setState(() => isExp ? _expanded.remove(id) : _expanded.add(id)),
                                          child: Row(children: [
                                            Text(isExp ? 'Réduire' : 'Voir membres',
                                              style: const TextStyle(color: AppTheme.primaryLight, fontSize: 12, fontWeight: FontWeight.w600)),
                                            const SizedBox(width: 4),
                                            Icon(isExp ? Icons.expand_less : Icons.expand_more, color: AppTheme.primaryLight, size: 16),
                                          ]),
                                        ),
                                    ]),

                                    if (isExp && agents.isNotEmpty) ...[
                                      const SizedBox(height: 10),
                                      Wrap(
                                        spacing: 6, runSpacing: 6,
                                        children: agents.map((aId) {
                                          final shortId = aId.toString().length >= 6
                                              ? aId.toString().substring(aId.toString().length - 6).toUpperCase()
                                              : aId.toString().toUpperCase();
                                          return Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                                            decoration: BoxDecoration(
                                              color: AppTheme.surfaceElevated,
                                              borderRadius: BorderRadius.circular(8),
                                              border: Border.all(color: const Color(0xFF27354A)),
                                            ),
                                            child: Text('#$shortId',
                                              style: const TextStyle(color: AppTheme.textSecondary, fontSize: 11, fontFamily: 'monospace')),
                                          );
                                        }).toList(),
                                      ),
                                    ],
                                  ]),
                                ),
                              ],
                            ),
                          );
                        },
                      ),
                    ),
    );
  }
}
