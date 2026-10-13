import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../../core/theme/app_theme.dart';
import '../providers/ticket_provider.dart';
import '../../data/models/ticket_model.dart';
import 'create_ticket_screen.dart';
import 'ticket_detail_screen.dart';

class TicketListScreen extends StatefulWidget {
  const TicketListScreen({super.key});

  @override
  State<TicketListScreen> createState() => _TicketListScreenState();
}

class _TicketListScreenState extends State<TicketListScreen> {
  String _selectedFilter = 'ALL';
  final TextEditingController _searchController = TextEditingController();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<TicketProvider>().fetchTickets();
    });
  }

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final ticketProvider = context.watch<TicketProvider>();

    final filteredTickets = ticketProvider.tickets.where((ticket) {
      if (_selectedFilter != 'ALL' && ticket.status.toUpperCase() != _selectedFilter) {
        return false;
      }
      final query = _searchController.text.trim().toLowerCase();
      if (query.isNotEmpty) {
        final matchesSubject = ticket.subject.toLowerCase().contains(query);
        final matchesCategory = ticket.category.toLowerCase().contains(query);
        return matchesSubject || matchesCategory;
      }
      return true;
    }).toList();

    return Scaffold(
      appBar: AppBar(
        titleSpacing: 16,
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Mes Demandes & Tickets',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, letterSpacing: -0.3),
            ),
            Text(
              'Suivi en direct des incidents IT',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, size: 22),
            onPressed: () => ticketProvider.fetchTickets(),
          ),
          const SizedBox(width: 8),
        ],
      ),
      floatingActionButton: Container(
        decoration: BoxDecoration(
          gradient: AppTheme.primaryGradient,
          borderRadius: BorderRadius.circular(16),
          boxShadow: [
            BoxShadow(
              color: AppTheme.primary.withValues(alpha: 0.35),
              blurRadius: 18,
              offset: const Offset(0, 6),
            ),
          ],
        ),
        child: FloatingActionButton.extended(
          backgroundColor: Colors.transparent,
          elevation: 0,
          highlightElevation: 0,
          icon: const Icon(Icons.add_rounded, color: Colors.white, size: 22),
          label: const Text(
            'Nouveau ticket',
            style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14),
          ),
          onPressed: () {
            Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => const CreateTicketScreen()),
            );
          },
        ),
      ),
      body: Column(
        children: [
          // Barre de recherche et filtres rapides
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
            child: TextField(
              controller: _searchController,
              onChanged: (_) => setState(() {}),
              decoration: InputDecoration(
                hintText: 'Rechercher par mot-clé ou catégorie...',
                prefixIcon: const Icon(Icons.search_rounded, color: AppTheme.textSecondary, size: 20),
                suffixIcon: _searchController.text.isNotEmpty
                    ? IconButton(
                        icon: const Icon(Icons.clear, size: 18, color: AppTheme.textSecondary),
                        onPressed: () {
                          _searchController.clear();
                          setState(() {});
                        },
                      )
                    : null,
                contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              ),
            ),
          ),

          // Chips de filtrage rapide de statut
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
            child: Row(
              children: [
                _buildFilterChip('Tous', 'ALL'),
                const SizedBox(width: 8),
                _buildFilterChip('Ouverts', 'OPEN'),
                const SizedBox(width: 8),
                _buildFilterChip('En cours', 'IN_PROGRESS'),
                const SizedBox(width: 8),
                _buildFilterChip('Résolus', 'RESOLVED'),
                const SizedBox(width: 8),
                _buildFilterChip('Fermés', 'CLOSED'),
              ],
            ),
          ),

          const SizedBox(height: 6),

          // Liste des tickets
          Expanded(
            child: RefreshIndicator(
              onRefresh: () => ticketProvider.fetchTickets(),
              child: ticketProvider.isLoading && ticketProvider.tickets.isEmpty
                  ? const Center(child: CircularProgressIndicator())
                  : filteredTickets.isEmpty
                      ? Center(
                          child: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            children: [
                              Container(
                                width: 80,
                                height: 80,
                                decoration: BoxDecoration(
                                  color: AppTheme.surfaceElevated,
                                  shape: BoxShape.circle,
                                  border: Border.all(color: const Color(0xFF27354A)),
                                ),
                                child: Icon(
                                  Icons.inbox_outlined,
                                  size: 40,
                                  color: AppTheme.textSecondary.withValues(alpha: 0.6),
                                ),
                              ),
                              const SizedBox(height: 16),
                              const Text(
                                'Aucun ticket trouvé',
                                style: TextStyle(
                                  color: AppTheme.textPrimary,
                                  fontSize: 16,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              const SizedBox(height: 6),
                              Text(
                                _selectedFilter == 'ALL'
                                    ? 'Vous n\'avez soumis aucune demande pour l\'instant.'
                                    : 'Aucun ticket ne correspond à ce filtre.',
                                style: const TextStyle(color: AppTheme.textSecondary, fontSize: 13),
                              ),
                            ],
                          ),
                        )
                      : ListView.builder(
                          padding: const EdgeInsets.fromLTRB(16, 8, 16, 90),
                          itemCount: filteredTickets.length,
                          itemBuilder: (context, index) {
                            final ticket = filteredTickets[index];
                            return _buildTicketCard(ticket);
                          },
                        ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterChip(String label, String value) {
    final isSelected = _selectedFilter == value;
    return GestureDetector(
      onTap: () => setState(() => _selectedFilter = value),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 150),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.primary : AppTheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: isSelected ? AppTheme.primaryLight : const Color(0xFF27354A),
          ),
        ),
        child: Text(
          label,
          style: TextStyle(
            fontSize: 12,
            fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
            color: isSelected ? Colors.white : AppTheme.textSecondary,
          ),
        ),
      ),
    );
  }

  Widget _buildTicketCard(TicketModel ticket) {
    Color statusColor;
    String statusLabel;
    switch (ticket.status.toUpperCase()) {
      case 'OPEN':
        statusColor = const Color(0xFF38BDF8); // Sky blue
        statusLabel = 'OUVERT';
        break;
      case 'IN_PROGRESS':
        statusColor = AppTheme.warning;
        statusLabel = 'EN COURS';
        break;
      case 'RESOLVED':
        statusColor = AppTheme.success;
        statusLabel = 'RÉSOLU';
        break;
      case 'CLOSED':
        statusColor = AppTheme.textMuted;
        statusLabel = 'FERMÉ';
        break;
      default:
        statusColor = AppTheme.textSecondary;
        statusLabel = ticket.status.toUpperCase();
    }

    Color priorityColor;
    switch (ticket.priority.toUpperCase()) {
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

    final dateStr = DateFormat('dd/MM/yyyy HH:mm').format(ticket.createdAt);

    return GestureDetector(
      onTap: () {
        Navigator.of(context).push(
          MaterialPageRoute(
            builder: (_) => TicketDetailScreen(ticketId: ticket.id),
          ),
        );
      },
      child: Container(
        margin: const EdgeInsets.only(bottom: 14),
        decoration: BoxDecoration(
          color: AppTheme.surface,
          borderRadius: BorderRadius.circular(18),
          border: Border.all(color: const Color(0xFF1F293D)),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.2),
              blurRadius: 12,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
            // Header Row: Status Pill & Priority Badge
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
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 6,
                        height: 6,
                        decoration: BoxDecoration(
                          color: statusColor,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        statusLabel,
                        style: TextStyle(
                          color: statusColor,
                          fontSize: 11,
                          fontWeight: FontWeight.bold,
                          letterSpacing: 0.3,
                        ),
                      ),
                    ],
                  ),
                ),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: priorityColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    ticket.priority.toUpperCase(),
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

            // Subject
            Text(
              ticket.subject,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.bold,
                color: AppTheme.textPrimary,
                letterSpacing: -0.2,
              ),
            ),
            const SizedBox(height: 6),

            // Description preview
            Text(
              ticket.description,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 13,
                color: AppTheme.textSecondary.withValues(alpha: 0.9),
                height: 1.35,
              ),
            ),
            const SizedBox(height: 12),

            // Footer: Category chip & Creation Date
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: AppTheme.surfaceElevated,
                    borderRadius: BorderRadius.circular(6),
                    border: Border.all(color: const Color(0xFF27354A)),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      const Icon(Icons.label_outline, size: 12, color: AppTheme.textSecondary),
                      const SizedBox(width: 4),
                      Text(
                        ticket.category,
                        style: const TextStyle(fontSize: 11, color: AppTheme.textSecondary),
                      ),
                    ],
                  ),
                ),
                Text(
                  dateStr,
                  style: const TextStyle(fontSize: 11, color: AppTheme.textMuted),
                ),
              ],
            ),

            // Resolution Note block if exists
            if (ticket.resolutionNote != null && ticket.resolutionNote!.isNotEmpty) ...[
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: AppTheme.success.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(color: AppTheme.success.withValues(alpha: 0.3)),
                ),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Icon(Icons.check_circle_rounded, size: 16, color: AppTheme.success),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'Résolution : ${ticket.resolutionNote}',
                        style: const TextStyle(fontSize: 12, color: AppTheme.success, height: 1.3),
                      ),
                    ),
                  ],
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
