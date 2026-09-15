import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../providers/auth_provider.dart';
import '../auth/login_screen.dart';

class ProfileScreen extends StatelessWidget {
  const ProfileScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final authProvider = context.watch<AuthProvider>();
    final user = authProvider.currentUser;

    return Scaffold(
      appBar: AppBar(title: const Text('Mon Profil')),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(
          children: [
            const SizedBox(height: 20),
            CircleAvatar(
              radius: 44,
              backgroundColor: AppTheme.primary,
              child: Text(
                (user?.fullName?.isNotEmpty == true ? user!.fullName![0] : 'U').toUpperCase(),
                style: const TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white),
              ),
            ),
            const SizedBox(height: 16),
            Text(
              user?.fullName ?? 'Utilisateur GEISER',
              style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
            ),
            const SizedBox(height: 4),
            Text(
              user?.email ?? '',
              style: const TextStyle(fontSize: 14, color: AppTheme.textSecondary),
            ),
            const SizedBox(height: 8),
            Chip(
              label: Text(
                user?.role ?? 'USER',
                style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold),
              ),
              backgroundColor: AppTheme.primaryDark.withOpacity(0.5),
              side: BorderSide.none,
            ),
            const SizedBox(height: 32),
            Card(
              child: Column(
                children: [
                  ListTile(
                    leading: const Icon(Icons.storage, color: AppTheme.accent),
                    title: const Text('Serveur API Backend'),
                    subtitle: const Text('FastAPI (localhost:8000)'),
                  ),
                  const Divider(height: 1, color: AppTheme.surfaceLight),
                  ListTile(
                    leading: const Icon(Icons.memory, color: AppTheme.accent),
                    title: const Text('Moteur IA RAG'),
                    subtitle: const Text('FAISS MiniLM-L12 + Gemma 3'),
                  ),
                  const Divider(height: 1, color: AppTheme.surfaceLight),
                  ListTile(
                    leading: const Icon(Icons.verified_user_outlined, color: AppTheme.accent),
                    title: const Text('Certification'),
                    subtitle: const Text('ISO/IEC 27001 Standard'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
            ElevatedButton.icon(
              style: ElevatedButton.styleFrom(
                backgroundColor: AppTheme.error.withOpacity(0.15),
                foregroundColor: AppTheme.error,
                side: const BorderSide(color: AppTheme.error),
              ),
              icon: const Icon(Icons.logout),
              label: const Text('Se déconnecter'),
              onPressed: () async {
                await authProvider.logout();
                if (context.mounted) {
                  Navigator.of(context).pushAndRemoveUntil(
                    MaterialPageRoute(builder: (_) => const LoginScreen()),
                    (route) => false,
                  );
                }
              },
            ),
          ],
        ),
      ),
    );
  }
}
