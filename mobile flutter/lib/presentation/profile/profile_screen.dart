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
      setState(() { _twoFAFlow = 'enable_sent'; _twoFASuccess = 'Code envoyé à votre adresse e-mail.'; });
    } catch (e) {
      setState(() => _twoFAError = e.toString().replaceAll('Exception: ', ''));
    } finally {
      setState(() => _loading2FA = false);
    }
  }

  // ── Enable Step 2 ─────────────────────────────────────────────────
  Future<void> _handleEnableConfirm() async {
    if (_codeController.text.length != 6) {
      setState(() => _twoFAError = 'Veuillez saisir le code à 6 chiffres.');
      return;
    }
    setState(() { _loading2FA = true; _twoFAError = ''; });
    try {
      await AuthApiService.confirmEnable2FA(_codeController.text);
      setState(() { _twoFAEnabled = true; _twoFAFlow = 'idle'; _twoFASuccess = '2FA activée avec succès ✓'; });
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
      setState(() => _twoFAError = 'Veuillez saisir votre mot de passe actuel.');
      return;
    }
    setState(() { _loading2FA = true; _twoFAError = ''; });
    try {
      await AuthApiService.requestDisable2FA(_passwordController.text);
      setState(() { _twoFAFlow = 'disable_otp'; _twoFASuccess = 'Mot de passe validé. Code envoyé par e-mail.'; });
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
      setState(() => _twoFAError = 'Veuillez saisir le code à 6 chiffres.');
      return;
    }
    setState(() { _loading2FA = true; _twoFAError = ''; });
    try {
      await AuthApiService.confirmDisable2FA(_codeController.text);
      setState(() { _twoFAEnabled = false; _twoFAFlow = 'idle'; _twoFASuccess = '2FA désactivée avec succès.'; });
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
      appBar: AppBar(
        titleSpacing: 16,
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Profil Utilisateur',
              style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, letterSpacing: -0.3),
            ),
            Text(
              'Paramètres du compte & Sécurité',
              style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
            ),
          ],
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
        child: Column(
          children: [
            // Header Profile Card
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
                children: [
                  // Avatar with Gradient
                  Container(
                    width: 76,
                    height: 76,
                    decoration: BoxDecoration(
                      gradient: AppTheme.primaryGradient,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: AppTheme.primary.withValues(alpha: 0.35),
                          blurRadius: 20,
                          offset: const Offset(0, 6),
                        ),
                      ],
                    ),
                    child: Center(
                      child: Text(
                        (user?.fullName?.isNotEmpty == true ? user!.fullName![0] : 'U').toUpperCase(),
                        style: const TextStyle(fontSize: 30, fontWeight: FontWeight.bold, color: Colors.white),
                      ),
                    ),
                  ),
                  const SizedBox(height: 14),
                  Text(
                    user?.fullName ?? 'Utilisateur GEISER',
                    style: const TextStyle(fontSize: 19, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    user?.email ?? '',
                    style: const TextStyle(fontSize: 13, color: AppTheme.textSecondary),
                  ),
                  const SizedBox(height: 10),
                  Container(
                    padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
                    decoration: BoxDecoration(
                      color: AppTheme.primaryDark.withValues(alpha: 0.4),
                      borderRadius: BorderRadius.circular(20),
                      border: Border.all(color: AppTheme.primaryLight.withValues(alpha: 0.4)),
                    ),
                    child: Text(
                      user?.role ?? 'USER',
                      style: const TextStyle(
                        fontSize: 11,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryLight,
                        letterSpacing: 0.5,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 20),

            // ── 2FA CARD ─────────────────────────────────────────────
            Container(
              padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFF1F293D)),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.all(8),
                        decoration: BoxDecoration(
                          color: ((_twoFAEnabled ?? false) ? AppTheme.success : AppTheme.warning).withValues(alpha: 0.15),
                          borderRadius: BorderRadius.circular(10),
                        ),
                        child: Icon(
                          Icons.security_rounded,
                          color: (_twoFAEnabled ?? false) ? AppTheme.success : AppTheme.warning,
                          size: 20,
                        ),
                      ),
                      const SizedBox(width: 12),
                      const Expanded(
                        child: Text(
                          'Double Facteur (2FA)',
                          style: TextStyle(
                            fontSize: 15,
                            fontWeight: FontWeight.bold,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ),
                      if (_twoFAEnabled != null)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: (_twoFAEnabled! ? AppTheme.success : AppTheme.warning).withValues(alpha: 0.12),
                            borderRadius: BorderRadius.circular(20),
                            border: Border.all(
                              color: (_twoFAEnabled! ? AppTheme.success : AppTheme.warning).withValues(alpha: 0.4),
                            ),
                          ),
                          child: Text(
                            _twoFAEnabled! ? 'ACTIF' : 'INACTIF',
                            style: TextStyle(
                              fontSize: 11,
                              color: _twoFAEnabled! ? AppTheme.success : AppTheme.warning,
                              fontWeight: FontWeight.bold,
                            ),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 12),

                  // Messages succès / erreur
                  if (_twoFASuccess.isNotEmpty)
                    Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppTheme.success.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppTheme.success.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.check_circle_rounded, color: AppTheme.success, size: 16),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _twoFASuccess,
                              style: const TextStyle(color: AppTheme.success, fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                    ),
                  if (_twoFAError.isNotEmpty)
                    Container(
                      margin: const EdgeInsets.only(bottom: 12),
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: AppTheme.error.withValues(alpha: 0.1),
                        borderRadius: BorderRadius.circular(10),
                        border: Border.all(color: AppTheme.error.withValues(alpha: 0.3)),
                      ),
                      child: Row(
                        children: [
                          const Icon(Icons.error_outline_rounded, color: AppTheme.error, size: 16),
                          const SizedBox(width: 8),
                          Expanded(
                            child: Text(
                              _twoFAError,
                              style: const TextStyle(color: AppTheme.error, fontSize: 13),
                            ),
                          ),
                        ],
                      ),
                    ),

                  // ── IDLE state ─────────────────────────────────
                  if (_twoFAFlow == 'idle' && _twoFAEnabled != null) ...[
                    Text(
                      _twoFAEnabled!
                          ? 'Chaque connexion exige un code de sécurité à 6 chiffres transmis par e-mail.'
                          : 'Activez l\'authentification double facteur pour sécuriser les accès à vos tickets.',
                      style: TextStyle(fontSize: 13, color: AppTheme.textSecondary.withValues(alpha: 0.9), height: 1.35),
                    ),
                    const SizedBox(height: 16),
                    if (!_twoFAEnabled!)
                      ElevatedButton.icon(
                        icon: _loading2FA
                            ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                            : const Icon(Icons.shield_outlined, size: 16),
                        label: const Text('Activer la 2FA'),
                        onPressed: _loading2FA ? null : _handleEnableRequest,
                      )
                    else
                      OutlinedButton.icon(
                        style: OutlinedButton.styleFrom(
                          foregroundColor: AppTheme.error,
                          side: const BorderSide(color: AppTheme.error),
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
                        ),
                        icon: const Icon(Icons.no_encryption_outlined, size: 16),
                        label: const Text('Désactiver la 2FA'),
                        onPressed: _loading2FA
                            ? null
                            : () => setState(() { _twoFAFlow = 'disable_pw'; _twoFAError = ''; _twoFASuccess = ''; }),
                      ),
                  ],

                  // ── ENABLE — OTP entry ─────────────────────────
                  if (_twoFAFlow == 'enable_sent') ...[
                    const Text(
                      'Étape 2 — Saisissez le code reçu par e-mail',
                      style: TextStyle(fontSize: 12, color: AppTheme.textSecondary),
                    ),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _codeController,
                      keyboardType: TextInputType.number,
                      maxLength: 6,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 22, letterSpacing: 8, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                      decoration: InputDecoration(
                        hintText: '______',
                        counterText: '',
                        filled: true,
                        fillColor: AppTheme.surfaceElevated,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      onChanged: (_) => setState(() => _twoFAError = ''),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        ElevatedButton(
                          onPressed: _loading2FA ? null : _handleEnableConfirm,
                          child: _loading2FA
                              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('Confirmer'),
                        ),
                        const SizedBox(width: 10),
                        TextButton(onPressed: _resetWizard, child: const Text('Annuler')),
                      ],
                    ),
                  ],

                  // ── DISABLE — Password entry ───────────────────
                  if (_twoFAFlow == 'disable_pw') ...[
                    const Text('Étape 1 — Confirmez avec votre mot de passe', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _passwordController,
                      obscureText: true,
                      decoration: InputDecoration(
                        labelText: 'Mot de passe actuel',
                        filled: true,
                        fillColor: AppTheme.surfaceElevated,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      onChanged: (_) => setState(() => _twoFAError = ''),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        ElevatedButton(
                          style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
                          onPressed: _loading2FA ? null : _handleDisableRequest,
                          child: _loading2FA
                              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('Envoyer le code'),
                        ),
                        const SizedBox(width: 10),
                        TextButton(onPressed: _resetWizard, child: const Text('Annuler')),
                      ],
                    ),
                  ],

                  // ── DISABLE — OTP confirmation ─────────────────
                  if (_twoFAFlow == 'disable_otp') ...[
                    const Text('Étape 2 — Entrez le code de confirmation', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                    const SizedBox(height: 10),
                    TextField(
                      controller: _codeController,
                      keyboardType: TextInputType.number,
                      maxLength: 6,
                      textAlign: TextAlign.center,
                      style: const TextStyle(fontSize: 22, letterSpacing: 8, fontWeight: FontWeight.bold, color: AppTheme.textPrimary),
                      decoration: InputDecoration(
                        hintText: '______',
                        counterText: '',
                        filled: true,
                        fillColor: AppTheme.surfaceElevated,
                        border: OutlineInputBorder(borderRadius: BorderRadius.circular(10)),
                      ),
                      onChanged: (_) => setState(() => _twoFAError = ''),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        ElevatedButton(
                          style: ElevatedButton.styleFrom(backgroundColor: AppTheme.error),
                          onPressed: _loading2FA ? null : _handleDisableConfirm,
                          child: _loading2FA
                              ? const SizedBox(width: 14, height: 14, child: CircularProgressIndicator(strokeWidth: 2, color: Colors.white))
                              : const Text('Désactiver'),
                        ),
                        const SizedBox(width: 10),
                        TextButton(onPressed: _resetWizard, child: const Text('Annuler')),
                      ],
                    ),
                  ],
                ],
              ),
            ),
            const SizedBox(height: 16),

            // ── System Specs Card ─────────────────────────────────────
            Container(
              decoration: BoxDecoration(
                color: AppTheme.surface,
                borderRadius: BorderRadius.circular(20),
                border: Border.all(color: const Color(0xFF1F293D)),
              ),
              child: const Column(
                children: [
                  ListTile(
                    leading: Icon(Icons.dns_rounded, color: AppTheme.primaryLight, size: 22),
                    title: Text('Serveur Backend API', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    subtitle: Text('FastAPI + MongoDB (localhost:8000)', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ),
                  Divider(height: 1, color: Color(0xFF1F293D)),
                  ListTile(
                    leading: Icon(Icons.memory_rounded, color: AppTheme.accentLight, size: 22),
                    title: Text('Moteur IA RAG & LLM', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    subtitle: Text('FAISS MiniLM-L12 + Gemma 3 / Llama 3', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ),
                  Divider(height: 1, color: Color(0xFF1F293D)),
                  ListTile(
                    leading: Icon(Icons.verified_user_rounded, color: AppTheme.success, size: 22),
                    title: Text('Sécurité & Conformité', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600)),
                    subtitle: Text('Standard ITIL v4 & 2FA OTP Email', style: TextStyle(fontSize: 12, color: AppTheme.textSecondary)),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 28),

            // ── Logout ────────────────────────────────────────────────
            SizedBox(
              width: double.infinity,
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  foregroundColor: AppTheme.error,
                  side: BorderSide(color: AppTheme.error.withValues(alpha: 0.5)),
                  backgroundColor: AppTheme.error.withValues(alpha: 0.08),
                  padding: const EdgeInsets.symmetric(vertical: 14),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
                ),
                icon: const Icon(Icons.logout_rounded, size: 18),
                label: const Text('Se déconnecter', style: TextStyle(fontSize: 15, fontWeight: FontWeight.bold)),
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
            ),
            const SizedBox(height: 20),
          ],
        ),
      ),
    );
  }
}
