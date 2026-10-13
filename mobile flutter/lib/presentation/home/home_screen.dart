import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../providers/auth_provider.dart';
import '../dashboard/dashboard_screen.dart';
import '../tickets/ticket_list_screen.dart';
import '../chat/chat_screen.dart';
import '../notifications/notifications_screen.dart';
import '../profile/profile_screen.dart';
import '../agents/agents_screen.dart';
import '../teams/teams_screen.dart';
import '../users/users_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  final List<Widget> _pages = const [
    DashboardScreen(),
    TicketListScreen(),
    ChatScreen(),
    NotificationsScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    final user = context.watch<AuthProvider>().currentUser;
    final isAdmin = user?.role == 'ADMIN';
    final isAgentOrAdmin = user?.role == 'ADMIN' || user?.role == 'AGENT';

    return Scaffold(
      drawer: isAgentOrAdmin ? _buildAdminDrawer(context, isAdmin) : null,
      appBar: PreferredSize(
        preferredSize: const Size.fromHeight(kToolbarHeight),
        child: AppBar(
          title: Text(
            _getTitleForIndex(_currentIndex),
            style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18),
          ),
          leading: isAgentOrAdmin
              ? Builder(
                  builder: (ctx) => IconButton(
                    icon: const Icon(Icons.menu_rounded, color: AppTheme.textPrimary),
                    onPressed: () => Scaffold.of(ctx).openDrawer(),
                    tooltip: 'Menu Administration',
                  ),
                )
              : null,
        ),
      ),
      body: IndexedStack(
        index: _currentIndex,
        children: _pages,
      ),
      bottomNavigationBar: Container(
        decoration: const BoxDecoration(
          color: AppTheme.surface,
          border: Border(
            top: BorderSide(
              color: Color(0xFF1F293D),
              width: 1,
            ),
          ),
        ),
        child: SafeArea(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            child: Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _buildNavItem(
                  index: 0,
                  icon: Icons.dashboard_outlined,
                  activeIcon: Icons.dashboard_rounded,
                  label: 'Stats',
                ),
                _buildNavItem(
                  index: 1,
                  icon: Icons.confirmation_number_outlined,
                  activeIcon: Icons.confirmation_number_rounded,
                  label: 'Tickets',
                ),
                _buildNavItem(
                  index: 2,
                  icon: Icons.smart_toy_outlined,
                  activeIcon: Icons.smart_toy_rounded,
                  label: 'IA',
                ),
                _buildNavItem(
                  index: 3,
                  icon: Icons.notifications_none_rounded,
                  activeIcon: Icons.notifications_rounded,
                  label: 'Alertes',
                ),
                _buildNavItem(
                  index: 4,
                  icon: Icons.person_outline_rounded,
                  activeIcon: Icons.person_rounded,
                  label: 'Profil',
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _getTitleForIndex(int idx) {
    switch (idx) {
      case 0:
        return 'Tableau de bord';
      case 1:
        return 'Support & Demandes';
      case 2:
        return 'Assistant IA Support';
      case 3:
        return 'Notifications';
      case 4:
        return 'Mon Compte';
      default:
        return 'GEISER';
    }
  }

  Widget _buildAdminDrawer(BuildContext context, bool isAdmin) {
    return Drawer(
      backgroundColor: AppTheme.surface,
      child: SafeArea(
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: const BoxDecoration(
                border: Border(bottom: BorderSide(color: Color(0xFF1F293D))),
              ),
              child: Row(
                children: [
                  Container(
                    width: 44,
                    height: 44,
                    decoration: BoxDecoration(
                      gradient: AppTheme.primaryGradient,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: const Icon(Icons.admin_panel_settings_rounded, color: Colors.white, size: 24),
                  ),
                  const SizedBox(width: 12),
                  const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Espace Opérations',
                        style: TextStyle(
                          color: AppTheme.textPrimary,
                          fontWeight: FontWeight.bold,
                          fontSize: 16,
                        ),
                      ),
                      Text(
                        'Gestion & Équipes',
                        style: TextStyle(color: AppTheme.textSecondary, fontSize: 12),
                      ),
                    ],
                  ),
                ],
              ),
            ),
            const SizedBox(height: 8),
            ListTile(
              leading: const Icon(Icons.support_agent_rounded, color: AppTheme.primaryLight),
              title: const Text('Gestion des Agents', style: TextStyle(color: AppTheme.textPrimary)),
              onTap: () {
                Navigator.pop(context);
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const AgentsScreen()),
                );
              },
            ),
            ListTile(
              leading: const Icon(Icons.groups_rounded, color: AppTheme.accentLight),
              title: const Text('Gestion des Équipes', style: TextStyle(color: AppTheme.textPrimary)),
              onTap: () {
                Navigator.pop(context);
                Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => const TeamsScreen()),
                );
              },
            ),
            if (isAdmin)
              ListTile(
                leading: const Icon(Icons.manage_accounts_rounded, color: Color(0xFF8B5CF6)),
                title: const Text('Gestion des Utilisateurs', style: TextStyle(color: AppTheme.textPrimary)),
                onTap: () {
                  Navigator.pop(context);
                  Navigator.of(context).push(
                    MaterialPageRoute(builder: (_) => const UsersScreen()),
                  );
                },
              ),
            const Spacer(),
            Padding(
              padding: const EdgeInsets.all(16.0),
              child: Text(
                'GEISER ITSM v1.0.0',
                style: TextStyle(color: AppTheme.textMuted.withValues(alpha: 0.6), fontSize: 11),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNavItem({
    required int index,
    required IconData icon,
    required IconData activeIcon,
    required String label,
  }) {
    final isSelected = _currentIndex == index;

    return GestureDetector(
      onTap: () => setState(() => _currentIndex = index),
      behavior: HitTestBehavior.opaque,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 6),
        decoration: BoxDecoration(
          color: isSelected
              ? AppTheme.primary.withValues(alpha: 0.15)
              : Colors.transparent,
          borderRadius: BorderRadius.circular(20),
          border: isSelected
              ? Border.all(color: AppTheme.primaryLight.withValues(alpha: 0.3), width: 1)
              : null,
        ),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              isSelected ? activeIcon : icon,
              color: isSelected ? AppTheme.primaryLight : AppTheme.textSecondary,
              size: 20,
            ),
            const SizedBox(height: 2),
            Text(
              label,
              style: TextStyle(
                color: isSelected ? AppTheme.primaryLight : AppTheme.textSecondary,
                fontWeight: isSelected ? FontWeight.bold : FontWeight.w500,
                fontSize: 11,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
