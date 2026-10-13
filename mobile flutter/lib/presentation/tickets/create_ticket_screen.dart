import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../providers/ticket_provider.dart';

class CreateTicketScreen extends StatefulWidget {
  const CreateTicketScreen({super.key});

  @override
  State<CreateTicketScreen> createState() => _CreateTicketScreenState();
}

class _CreateTicketScreenState extends State<CreateTicketScreen> {
  final _formKey = GlobalKey<FormState>();
  final _subjectController = TextEditingController();
  final _descriptionController = TextEditingController();
  String _category = 'Authentification';
  String _priority = 'MEDIUM';

  final List<Map<String, dynamic>> _categories = [
    {'name': 'Authentification', 'icon': Icons.lock_person_outlined},
    {'name': 'Réseau & VPN', 'icon': Icons.wifi_tethering_rounded},
    {'name': 'Matériel / Poste', 'icon': Icons.computer_rounded},
    {'name': 'Messagerie Outlook', 'icon': Icons.mail_outline_rounded},
    {'name': 'Logiciels / ERP', 'icon': Icons.apps_rounded},
    {'name': 'Sécurité', 'icon': Icons.security_rounded},
  ];

  final List<Map<String, dynamic>> _priorities = [
    {'value': 'LOW', 'label': 'Basse', 'color': AppTheme.accentLight},
    {'value': 'MEDIUM', 'label': 'Moyenne', 'color': AppTheme.warning},
    {'value': 'HIGH', 'label': 'Haute', 'color': Colors.deepOrangeAccent},
    {'value': 'CRITICAL', 'label': 'Critique (P1)', 'color': AppTheme.error},
  ];

  @override
  void dispose() {
    _subjectController.dispose();
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _handleSubmit() async {
    if (!_formKey.currentState!.validate()) return;

    final provider = context.read<TicketProvider>();
    final success = await provider.createTicket(
      subject: _subjectController.text.trim(),
      description: _descriptionController.text.trim(),
      category: _category,
      priority: _priority,
    );

    if (mounted) {
      if (success) {
        Navigator.of(context).pop();
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(
            content: Text('Ticket soumis au support avec succès'),
            backgroundColor: AppTheme.success,
          ),
        );
      } else {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(
            content: Text(provider.error ?? 'Erreur lors de la création'),
            backgroundColor: AppTheme.error,
          ),
        );
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final provider = context.watch<TicketProvider>();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Déclarer un Incident'),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, size: 18),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Form(
          key: _formKey,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Card container
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: AppTheme.surface,
                  borderRadius: BorderRadius.circular(20),
                  border: Border.all(color: const Color(0xFF1F293D)),
                  boxShadow: [
                    BoxShadow(
                      color: Colors.black.withValues(alpha: 0.2),
                      blurRadius: 18,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Détails de l\'incident',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.textPrimary,
                      ),
                    ),
                    const SizedBox(height: 16),

                    // Sujet
                    TextFormField(
                      controller: _subjectController,
                      decoration: const InputDecoration(
                        labelText: 'Objet de la demande *',
                        hintText: 'Ex: Accès bloqué sur SharePoint',
                        prefixIcon: Icon(Icons.title_rounded, color: AppTheme.textSecondary, size: 20),
                      ),
                      validator: (v) =>
                          v == null || v.trim().isEmpty ? 'Sujet requis' : null,
                    ),
                    const SizedBox(height: 18),

                    // Catégorie
                    const Text(
                      'Catégorie IT',
                      style: TextStyle(fontSize: 13, color: AppTheme.textSecondary, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 8),
                    DropdownButtonFormField<String>(
                      initialValue: _category,
                      decoration: const InputDecoration(
                        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      ),
                      dropdownColor: AppTheme.surfaceElevated,
                      items: _categories.map((c) {
                        return DropdownMenuItem<String>(
                          value: c['name'] as String,
                          child: Row(
                            children: [
                              Icon(c['icon'] as IconData, size: 18, color: AppTheme.primaryLight),
                              const SizedBox(width: 10),
                              Text(c['name'] as String),
                            ],
                          ),
                        );
                      }).toList(),
                      onChanged: (v) {
                        if (v != null) setState(() => _category = v);
                      },
                    ),
                    const SizedBox(height: 18),

                    // Priorité
                    const Text(
                      'Niveau d\'urgence / Priorité',
                      style: TextStyle(fontSize: 13, color: AppTheme.textSecondary, fontWeight: FontWeight.w600),
                    ),
                    const SizedBox(height: 8),
                    DropdownButtonFormField<String>(
                      initialValue: _priority,
                      decoration: const InputDecoration(
                        contentPadding: EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      ),
                      dropdownColor: AppTheme.surfaceElevated,
                      items: _priorities.map((p) {
                        final color = p['color'] as Color;
                        return DropdownMenuItem<String>(
                          value: p['value'] as String,
                          child: Row(
                            children: [
                              Container(
                                width: 8,
                                height: 8,
                                decoration: BoxDecoration(color: color, shape: BoxShape.circle),
                              ),
                              const SizedBox(width: 10),
                              Text(p['label'] as String),
                            ],
                          ),
                        );
                      }).toList(),
                      onChanged: (v) {
                        if (v != null) setState(() => _priority = v);
                      },
                    ),
                    const SizedBox(height: 18),

                    // Description
                    TextFormField(
                      controller: _descriptionController,
                      maxLines: 4,
                      decoration: const InputDecoration(
                        labelText: 'Description précise *',
                        hintText: 'Précisez l\'heure, les messages d\'erreur ou les démarches déjà tentées...',
                        alignLabelWithHint: true,
                      ),
                      validator: (v) =>
                          v == null || v.trim().isEmpty ? 'Description requise' : null,
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),

              // Bouton Soumettre
              Container(
                height: 52,
                decoration: BoxDecoration(
                  gradient: AppTheme.primaryGradient,
                  borderRadius: BorderRadius.circular(14),
                  boxShadow: [
                    BoxShadow(
                      color: AppTheme.primary.withValues(alpha: 0.35),
                      blurRadius: 16,
                      offset: const Offset(0, 6),
                    ),
                  ],
                ),
                child: ElevatedButton(
                  onPressed: provider.isLoading ? null : _handleSubmit,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.transparent,
                    shadowColor: Colors.transparent,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                  ),
                  child: provider.isLoading
                      ? const SizedBox(
                          width: 22,
                          height: 22,
                          child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white),
                        )
                      : const Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Icon(Icons.send_rounded, color: Colors.white, size: 18),
                            SizedBox(width: 8),
                            Text(
                              'Soumettre le ticket',
                              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Colors.white),
                            ),
                          ],
                        ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
