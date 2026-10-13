import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'core/theme/app_theme.dart';
import 'presentation/providers/auth_provider.dart';
import 'presentation/providers/chat_provider.dart';
import 'presentation/providers/ticket_provider.dart';
import 'presentation/auth/login_screen.dart';
import 'presentation/home/home_screen.dart';

class GeiserApp extends StatelessWidget {
  const GeiserApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        ChangeNotifierProvider(create: (_) => AuthProvider()),
        ChangeNotifierProvider(create: (_) => ChatProvider()),
        ChangeNotifierProvider(create: (_) => TicketProvider()),
      ],
      child: MaterialApp(
        title: 'GEISER Support IA',
        theme: AppTheme.darkTheme,
        debugShowCheckedModeBanner: false,
        home: const _AppRouter(),
      ),
    );
  }
}

/// Handles ONLY the initial boot auth check (token from SharedPreferences).
/// After boot, it NEVER rebuilds — LoginScreen owns all subsequent navigation.
/// This prevents Consumer<AuthProvider> from destroying LoginScreen mid-login.
class _AppRouter extends StatefulWidget {
  const _AppRouter();

  @override
  State<_AppRouter> createState() => _AppRouterState();
}

class _AppRouterState extends State<_AppRouter> {
  /// Set to true once the one-time boot token check is complete.
  bool _bootDone = false;

  /// The authenticated state captured at boot time.
  bool _bootAuthenticated = false;

  @override
  void initState() {
    super.initState();
    _awaitBootCheck();
  }

  void _awaitBootCheck() {
    final auth = context.read<AuthProvider>();

    if (!auth.isLoading) {
      // Auth check was already done synchronously (shouldn't normally happen)
      setState(() {
        _bootDone = true;
        _bootAuthenticated = auth.isAuthenticated;
      });
      return;
    }

    // Register a one-shot listener: fires on every notifyListeners() call,
    // but only acts the FIRST time isLoading becomes false (boot completion).
    late final VoidCallback listener;
    listener = () {
      if (!auth.isLoading) {
        auth.removeListener(listener);
        if (mounted) {
          setState(() {
            _bootDone = true;
            _bootAuthenticated = auth.isAuthenticated;
          });
        }
      }
    };
    auth.addListener(listener);
  }

  @override
  Widget build(BuildContext context) {
    // While the boot token-check is running, show a spinner.
    if (!_bootDone) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }

    // Boot done. Pick the correct start screen ONCE.
    // We do NOT call context.watch / context.select here, so this widget
    // never rebuilds again — login() notifyListeners() calls are harmless.
    if (_bootAuthenticated) {
      return const HomeScreen();
    }
    return const LoginScreen();
  }
}
