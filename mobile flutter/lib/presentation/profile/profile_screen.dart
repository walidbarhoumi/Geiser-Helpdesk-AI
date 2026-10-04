import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../../core/theme/app_theme.dart';
import '../providers/auth_provider.dart';
import '../auth/login_screen.dart';
import '../../data/services/auth_service.dart';

class ProfileScreen extends StatefulWidget {

  const ProfileScreen({super.key});

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  // ── 2FA state ────────────────────────────────────────────────────
  bool? _twoFAEnabled;
  bool _loading2FA = false;
  String _twoFAError = '';
  String _twoFASuccess = '';

  // Flow: 'idle' | 'enable_sent' | 'disable_pw' | 'disable_otp'
  String _twoFAFlow = 'idle';

  final _codeController = TextEditingController();
  final _passwordController = TextEditingController();

  @override
  void initState() {
    super.initState();
    _fetch2FAStatus();
  }

  @override
  void dispose() {
    _codeController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  // ── Fetch live status ─────────────────────────────────────────────
  Future<void> _fetch2FAStatus() async {
    try {
      final status = await AuthApiService.get2FAStatus();
      if (mounted) setState(() => _twoFAEnabled = status);
    } catch (_) {
      if (mounted) setState(() => _twoFAEnabled = false);
    }
  }

  void _resetWizard() {
    _codeController.clear();
    _passwordController.clear();
    setState(() {
      _twoFAError = '';
      _twoFASuccess = '';
      _twoFAFlow = 'idle';
    });
  }

  // ── Enable Step 1 ─────────────────────────────────────────────────
  Future<void> _handleEnableRequest() async {
    setState(() { _loading2FA = true; _twoFAError = ''; });
    try {
      await AuthApiService.requestEnable2FA();
      setState(() { _twoFAFlow = 'enable_sent'; _twoFASuccess = 'Code sent to your email.'; });
    } catch (e) {
      setState(() => _twoFAError = e.toString().replaceAll('Exception: ', ''));
    } finally {
      setState(() => _loading2FA = false);
    }
  }

  // ── Enable Step 2 ─────────────────────────────────────────────────
  Future<void> _handleEnableConfirm() async {
    if (_codeController.text.length != 6) {
      setState(() => _twoFAError = 'Enter the 6-digit code.');
      return;
    }
    setState(() { _loading2FA = true; _twoFAError = ''; });
    try {
      await AuthApiService.confirmEnable2FA(_codeController.text);
      setState(() { _twoFAEnabled = true; _twoFAFlow = 'idle'; _twoFASuccess = '2FA enabled successfully ✓'; });
      _codeController.clear();
    } catch (e) {
      setState(() => _twoFAError = e.toString().replaceAll('Exception: ', ''));
    } finally {
      setState(() => _loading2FA = false);
    }
  }

  // ── Disable Step 1 ────────────────────────────────────────────────
  Future<void> _handleDisableRequest() async {
    if (_passwordController.text.isEmpty) {
      setState(() => _twoFAError = 'Enter your current password.');
      return;
    }
    setState(() { _loading2FA = true; _twoFAError = ''; });
    try {
      await AuthApiService.requestDisable2FA(_passwordController.text);
      setState(() { _twoFAFlow = 'disable_otp'; _twoFASuccess = 'Password verified. Code sent to your email.'; });
      _passwordController.clear();
    } catch (e) {
      setState(() => _twoFAError = e.toString().replaceAll('Exception: ', ''));
    } finally {
      setState(() => _loading2FA = false);
    }
  }

  // ── Disable Step 2 ────────────────────────────────────────────────
  Future<void> _handleDisableConfirm() async {
    if (_codeController.text.length != 6) {
      setState(() => _twoFAError = 'Enter the 6-digit code.');
      return;
    }
    setState(() { _loading2FA = true; _twoFAError = ''; });
    try {
      await AuthApiService.confirmDisable2FA(_codeController.text);
      setState(() { _twoFAEnabled = false; _twoFAFlow = 'idle'; _twoFASuccess = '2FA has been disabled.'; });
      _codeController.clear();
    } catch (e) {
      setState(() => _twoFAError = e.toString().replaceAll('Exception: ', ''));
    } finally {
      setState(() => _loading2FA = false);
    }
  }

  // ── Build ─────────────────────────────────────────────────────────
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
            // Avatar
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
            Text(user?.email ?? '', style: const TextStyle(fontSize: 14, color: AppTheme.textSecondary)),
            const SizedBox(height: 8),
            Chip(
              label: Text(user?.role ?? 'USER',
                  style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold)),
              backgroundColor: AppTheme.primaryDark.withOpacity(0.5),
              side: BorderSide.none,
            ),
            const SizedBox(height: 32),

            // ── 2FA CARD ─────────────────────────────────────────────
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(Icons.security,
                            color: (_twoFAEnabled ?? false) ? Colors.green : Colors.orange),
                        const SizedBox(width: 10),
                        const Text('Authentification à deux facteurs',
                            style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold,
                                color: AppTheme.textPrimary)),
                        const Spacer(),
                        // Live status chip
                        if (_twoFAEnabled != null)
                          Chip(
                            label: Text(
                              _twoFAEnabled! ? 'ACTIF' : 'INACTIF',
                              style: TextStyle(
                                  fontSize: 11,
                                  color: _twoFAEnabled! ? Colors.green : Colors.orange,
                                  fontWeight: FontWeight.bold),
                            ),
                            backgroundColor: (_twoFAEnabled!
                                ? Colors.green
                                : Colors.orange).withOpacity(0.1),
                            side: BorderSide(
                                color: _twoFAEnabled! ? Colors.green : Colors.orange,
                                width: 1),
                          ),
                      ],
                    ),
                    const SizedBox(height: 8),

                    // Success / error messages
                    if (_twoFASuccess.isNotEmpty)
                      Container(
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                            color: Colors.green.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: Colors.green.withOpacity(0.3))),
                        child: Row(children: [
                          const Icon(Icons.check_circle, color: Colors.green, size: 16),
                          const SizedBox(width: 8),
                          Expanded(child: Text(_twoFASuccess,
                              style: const TextStyle(color: Colors.green, fontSize: 13))),
                        ]),
                      ),
                    if (_twoFAError.isNotEmpty)
                      Container(
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.all(10),
                        decoration: BoxDecoration(
                            color: AppTheme.error.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(8),
                            border: Border.all(color: AppTheme.error.withOpacity(0.3))),
                        child: Row(children: [
                          Icon(Icons.error_outline, color: AppTheme.error, size: 16),
                          const SizedBox(width: 8),
                          Expanded(child: Text(_twoFAError,
                              style: TextStyle(color: AppTheme.error, fontSize: 13))),
                        ]),
                      ),

                    // ── IDLE state ─────────────────────────────────
                    if (_twoFAFlow == 'idle' && _twoFAEnabled != null) ...[
                      Text(
                        _twoFAEnabled!
                            ? 'Chaque connexion requiert un code à 6 chiffres envoyé par email.'
                            : 'Activez la 2FA pour mieux protéger votre compte.',
                        style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                      ),
                      const SizedBox(height: 14),
                      if (!_twoFAEnabled!)
                        ElevatedButton.icon(
                          icon: _loading2FA
                              ? const SizedBox(width: 14, height: 14,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Icon(Icons.shield, size: 16),
                          label: const Text('Activer la 2FA'),
                          onPressed: _loading2FA ? null : _handleEnableRequest,
                        )
                      else
                        OutlinedButton.icon(
                          style: OutlinedButton.styleFrom(foregroundColor: AppTheme.error,
                              side: BorderSide(color: AppTheme.error)),
                          icon: const Icon(Icons.no_encryption, size: 16),
                          label: const Text('Désactiver la 2FA'),
                          onPressed: _loading2FA ? null
                              : () => setState(() { _twoFAFlow = 'disable_pw'; _twoFAError = ''; _twoFASuccess = ''; }),
                        ),
                    ],

                    // ── ENABLE — OTP entry ─────────────────────────
                    if (_twoFAFlow == 'enable_sent') ...[
                      const Text('Étape 2 — Entrez le code reçu par email',
                          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _codeController,
                        keyboardType: TextInputType.number,
                        maxLength: 6,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 22, letterSpacing: 8,
                            fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                        decoration: InputDecoration(
                          hintText: '_ _ _ _ _ _',
                          counterText: '',
                          filled: true,
                          fillColor: AppTheme.surfaceLight,
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        onChanged: (_) => setState(() => _twoFAError = ''),
                      ),
                      const SizedBox(height: 12),
                      Row(children: [
                        ElevatedButton(
                          onPressed: _loading2FA ? null : _handleEnableConfirm,
                          child: _loading2FA
                              ? const SizedBox(width: 14, height: 14,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('Confirmer l\'activation'),
                        ),
                        const SizedBox(width: 10),
                        TextButton(
                          onPressed: _resetWizard,
                          child: const Text('Annuler'),
                        ),
                      ]),
                    ],

                    // ── DISABLE — Password entry ───────────────────
                    if (_twoFAFlow == 'disable_pw') ...[
                      const Text('Étape 1 — Confirmez votre identité',
                          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _passwordController,
                        obscureText: true,
                        decoration: InputDecoration(
                          labelText: 'Mot de passe actuel',
                          filled: true,
                          fillColor: AppTheme.surfaceLight,
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        onChanged: (_) => setState(() => _twoFAError = ''),
                      ),
                      const SizedBox(height: 12),
                      Row(children: [
                        ElevatedButton(
                          style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
                          onPressed: _loading2FA ? null : _handleDisableRequest,
                          child: _loading2FA
                              ? const SizedBox(width: 14, height: 14,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('Vérifier et envoyer le code'),
                        ),
                        const SizedBox(width: 10),
                        TextButton(onPressed: _resetWizard, child: const Text('Annuler')),
                      ]),
                    ],

                    // ── DISABLE — OTP confirmation ─────────────────
                    if (_twoFAFlow == 'disable_otp') ...[
                      const Text('Étape 2 — Entrez le code reçu par email',
                          style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                      const SizedBox(height: 10),
                      TextField(
                        controller: _codeController,
                        keyboardType: TextInputType.number,
                        maxLength: 6,
                        textAlign: TextAlign.center,
                        style: const TextStyle(fontSize: 22, letterSpacing: 8,
                            fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                        decoration: InputDecoration(
                          hintText: '_ _ _ _ _ _',
                          counterText: '',
                          filled: true,
                          fillColor: AppTheme.surfaceLight,
                          border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                        ),
                        onChanged: (_) => setState(() => _twoFAError = ''),
                      ),
                      const SizedBox(height: 12),
                      Row(children: [
                        ElevatedButton(
                          style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
                          onPressed: _loading2FA ? null : _handleDisableConfirm,
                          child: _loading2FA
                              ? const SizedBox(width: 14, height: 14,
                                  child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('Confirmer la désactivation'),
                        ),
                        const SizedBox(width: 10),
                        TextButton(onPressed: _resetWizard, child: const Text('Annuler')),
                      ]),
                    ],
                  ],
                ),
              ),
            ),

            const SizedBox(height: 16),

            // ── Info card ─────────────────────────────────────────────
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

            // ── Logout ────────────────────────────────────────────────
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
