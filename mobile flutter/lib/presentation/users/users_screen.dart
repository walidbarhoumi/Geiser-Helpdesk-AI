import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../../core/constants/api_constants.dart';
import '../../data/services/api_client.dart';
import '../providers/auth_provider.dart';

class UsersScreen extends StatefulWidget {
  const UsersScreen({super.key});

  @override
  State<UsersScreen> createState() => _UsersScreenState();
}

class _UsersScreenState extends State<UsersScreen> {
  bool _loading = true;
  String? _error;
  List<dynamic> _users = [];
  String _search = '';

  @override
  void initState() {
    super.initState();
    _fetch();
  }

  Future<void> _fetch() async {
    setState(() { _loading = true; _error = null; });
    try {
      final res = await ApiClient().dio.get(ApiConstants.users);
      _users = res.data is List ? res.data as List<dynamic> : [];
    } catch (_) {
      _error = 'Accès refusé ou erreur serveur';
    }
    if (mounted) setState(() => _loading = false);
  }

  Future<void> _toggleActive(String id, bool current) async {
    try {
      await ApiClient().dio.put('/users/$id', data: {'is_active': !current});
      _fetch();
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Erreur lors de la mise à jour')),
        );
      }
    }
  }

  Future<void> _deleteUser(String id) async {
    final confirm = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        backgroundColor: AppTheme.surfaceElevated,
        title: const Text('Supprimer l\'utilisateur', style: TextStyle(color: AppTheme.textPrimary)),
        content: const Text('Cette action est irréversible.', style: TextStyle(color: AppTheme.textSecondary)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Annuler')),
          TextButton(onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Supprimer', style: TextStyle(color: AppTheme.error))),
        ],
      ),
    );
    if (confirm == true) {
      try {
        await ApiClient().dio.delete('/users/$id');
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

  List<dynamic> get _filtered => _users.where((u) {
    final q = _search.toLowerCase();
    if (q.isEmpty) return true;
    final email = (u['email'] as String? ?? '').toLowerCase();
    final name = (u['full_name'] as String? ?? '').toLowerCase();
    return email.contains(q) || name.contains(q);
  }).toList();

  @override
  Widget build(BuildContext context) {
    final me = context.read<AuthProvider>().currentUser;
    final isAdmin = me?.role == 'ADMIN';

    if (!isAdmin) {
      return Scaffold(
        appBar: AppBar(title: const Text('Utilisateurs')),
        body: const Center(
          child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
            Icon(Icons.lock_rounded, color: AppTheme.error, size: 56),
            SizedBox(height: 16),
            Text('Accès réservé aux administrateurs',
              textAlign: TextAlign.center,
              style: TextStyle(color: AppTheme.textSecondary, fontSize: 15)),
          ]),
        ),
      );
    }

    final filtered = _filtered;
    final totalActive = _users.where((u) => u['is_active'] == true).length;
    final totalAdmins = _users.where((u) => u['role'] == 'ADMIN').length;

    return Scaffold(
      appBar: AppBar(
        title: const Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('Utilisateurs', style: TextStyle(fontSize: 17, fontWeight: FontWeight.bold)),
          Text('Gestion des comptes', style: TextStyle(fontSize: 11, color: AppTheme.textSecondary)),
        ]),
        actions: [
          IconButton(icon: const Icon(Icons.refresh_rounded, size: 22), onPressed: _fetch),
          const SizedBox(width: 8),
        ],
      ),
      body: Column(
        children: [
          // Stats row
          if (!_loading && _error == null)
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 10, 16, 4),
              child: Row(children: [
                _StatChip(label: 'Total', value: '${_users.length}', color: AppTheme.primary),
                const SizedBox(width: 8),
                _StatChip(label: 'Actifs', value: '$totalActive', color: AppTheme.success),
                const SizedBox(width: 8),
                _StatChip(label: 'Admins', value: '$totalAdmins', color: const Color(0xFF8B5CF6)),
              ]),
            ),

          // Search
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
            child: TextField(
              onChanged: (v) => setState(() => _search = v),
              style: const TextStyle(color: AppTheme.textPrimary),
              decoration: const InputDecoration(
                hintText: 'Rechercher par nom ou email...',
                prefixIcon: Icon(Icons.search_rounded, color: AppTheme.textSecondary, size: 20),
                contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
            ),
          ),

          Expanded(
            child: _loading
                ? const Center(child: CircularProgressIndicator())
                : _error != null
                    ? Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                        const Icon(Icons.lock_rounded, color: AppTheme.error, size: 48),
                        const SizedBox(height: 12),
                        Text(_error!, style: const TextStyle(color: AppTheme.textSecondary)),
                        const SizedBox(height: 12),
                        ElevatedButton(onPressed: _fetch, child: const Text('Réessayer')),
                      ]))
                    : filtered.isEmpty
                        ? const Center(child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
                            Icon(Icons.person_search_rounded, color: AppTheme.textMuted, size: 48),
                            SizedBox(height: 12),
                            Text('Aucun utilisateur trouvé', style: TextStyle(color: AppTheme.textSecondary)),
                          ]))
                        : RefreshIndicator(
                            onRefresh: _fetch, color: AppTheme.primaryLight,
                            child: ListView.builder(
                              padding: const EdgeInsets.fromLTRB(16, 4, 16, 24),
                              itemCount: filtered.length,
                              itemBuilder: (context, i) {
                                final u = filtered[i] as Map<String, dynamic>;
                                final uid = u['id'] as String? ?? '';
                                final email = u['email'] as String? ?? '';
                                final name = u['full_name'] as String? ?? '';
                                final role = u['role'] as String? ?? 'USER';
                                final isActive = u['is_active'] as bool? ?? true;
                                final has2FA = u['two_factor_enabled'] as bool? ?? false;
                                final isSelf = uid == me?.id;

                                Color roleColor;
                                switch (role) {
                                  case 'ADMIN': roleColor = const Color(0xFF8B5CF6); break;
                                  case 'AGENT': roleColor = AppTheme.info; break;
                                  default: roleColor = AppTheme.textMuted;
                                }

                                final initials = name.isNotEmpty
                                    ? name.trim().split(' ').take(2).map((p) => p.isNotEmpty ? p[0].toUpperCase() : '').join()
                                    : email.isNotEmpty ? email[0].toUpperCase() : '?';

                                return Container(
                                  margin: const EdgeInsets.only(bottom: 10),
                                  decoration: BoxDecoration(
                                    color: AppTheme.surface,
                                    borderRadius: BorderRadius.circular(16),
                                    border: Border.all(color: isSelf ? AppTheme.primary.withValues(alpha: 0.4) : const Color(0xFF1F293D)),
                                    boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.15), blurRadius: 8, offset: const Offset(0, 3))],
                                  ),
                                  padding: const EdgeInsets.all(14),
                                  child: Row(children: [
                                    // Avatar
                                    Container(
                                      width: 46, height: 46,
                                      decoration: BoxDecoration(
                                        color: roleColor.withValues(alpha: 0.15),
                                        shape: BoxShape.circle,
                                        border: Border.all(color: roleColor.withValues(alpha: 0.3)),
                                      ),
                                      child: Center(child: Text(initials,
                                        style: TextStyle(color: roleColor, fontWeight: FontWeight.bold, fontSize: 15))),
                                    ),
                                    const SizedBox(width: 12),
                                    Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                                      Row(children: [
                                        if (name.isNotEmpty)
                                          Text(name, style: const TextStyle(color: AppTheme.textPrimary, fontWeight: FontWeight.bold, fontSize: 14)),
                                        if (isSelf) ...[
                                          const SizedBox(width: 6),
                                          Container(padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                                            decoration: BoxDecoration(color: AppTheme.primary.withValues(alpha: 0.15), borderRadius: BorderRadius.circular(4)),
                                            child: const Text('Moi', style: TextStyle(color: AppTheme.primaryLight, fontSize: 10, fontWeight: FontWeight.bold))),
                                        ],
                                      ]),
                                      const SizedBox(height: 2),
                                      Text(email, style: const TextStyle(color: AppTheme.textSecondary, fontSize: 12), overflow: TextOverflow.ellipsis),
                                      const SizedBox(height: 6),
                                      Row(children: [
                                        // Role badge
                                        Container(padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                          decoration: BoxDecoration(color: roleColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6),
                                            border: Border.all(color: roleColor.withValues(alpha: 0.25))),
                                          child: Text(role, style: TextStyle(color: roleColor, fontSize: 10, fontWeight: FontWeight.bold))),
                                        const SizedBox(width: 6),
                                        // Status
                                        Container(width: 8, height: 8, decoration: BoxDecoration(
                                          color: isActive ? AppTheme.success : AppTheme.textMuted, shape: BoxShape.circle)),
                                        const SizedBox(width: 4),
                                        Text(isActive ? 'Actif' : 'Inactif',
                                          style: TextStyle(color: isActive ? AppTheme.success : AppTheme.textMuted, fontSize: 10, fontWeight: FontWeight.w600)),
                                        if (has2FA) ...[
                                          const SizedBox(width: 6),
                                          const Icon(Icons.shield_rounded, color: AppTheme.success, size: 12),
                                          const SizedBox(width: 2),
                                          const Text('2FA', style: TextStyle(color: AppTheme.success, fontSize: 10, fontWeight: FontWeight.w600)),
                                        ],
                                      ]),
                                    ])),
                                    if (!isSelf) Column(mainAxisSize: MainAxisSize.min, children: [
                                      IconButton(
                                        icon: Icon(isActive ? Icons.block_rounded : Icons.check_circle_rounded,
                                          color: isActive ? AppTheme.warning : AppTheme.success, size: 20),
                                        onPressed: () => _toggleActive(uid, isActive),
                                        padding: EdgeInsets.zero, constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                                        tooltip: isActive ? 'Désactiver' : 'Activer',
                                      ),
                                      IconButton(
                                        icon: const Icon(Icons.delete_outline_rounded, color: AppTheme.error, size: 20),
                                        onPressed: () => _deleteUser(uid),
                                        padding: EdgeInsets.zero, constraints: const BoxConstraints(minWidth: 32, minHeight: 32),
                                        tooltip: 'Supprimer',
                                      ),
                                    ]),
                                  ]),
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

class _StatChip extends StatelessWidget {
  final String label;
  final String value;
  final Color color;

  const _StatChip({required this.label, required this.value, required this.color});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: color.withValues(alpha: 0.25)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Text(value, style: TextStyle(color: color, fontWeight: FontWeight.bold, fontSize: 14)),
        const SizedBox(width: 4),
        Text(label, style: TextStyle(color: color.withValues(alpha: 0.7), fontSize: 11)),
      ]),
    );
  }
}
