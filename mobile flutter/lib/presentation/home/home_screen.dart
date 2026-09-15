import 'package:flutter/material.dart';
import '../../core/theme/app_theme.dart';
import '../chat/chat_screen.dart';
import '../tickets/ticket_list_screen.dart';
import '../profile/profile_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  int _currentIndex = 0;

  final List<Widget> _pages = const [
    ChatScreen(),
    TicketListScreen(),
    ProfileScreen(),
  ];

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: IndexedStack(
        index: _currentIndex,
        children: _pages,
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _currentIndex,
        onDestinationSelected: (index) {
          setState(() {
            _currentIndex = index;
          });
        },
        backgroundColor: AppTheme.surface,
        indicatorColor: AppTheme.primary.withOpacity(0.3),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline, color: AppTheme.textSecondary),
            selectedIcon: Icon(Icons.smart_toy_rounded, color: AppTheme.primaryLight),
            label: 'IA Support',
          ),
          NavigationDestination(
            icon: Icon(Icons.confirmation_number_outlined, color: AppTheme.textSecondary),
            selectedIcon: Icon(Icons.confirmation_number, color: AppTheme.primaryLight),
            label: 'Tickets',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline, color: AppTheme.textSecondary),
            selectedIcon: Icon(Icons.person, color: AppTheme.primaryLight),
            label: 'Profil',
          ),
        ],
      ),
    );
  }
}
