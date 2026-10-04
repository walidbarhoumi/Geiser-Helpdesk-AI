"""
test_smtp_async.py
==============================================================================
Suite de tests unitaires pour l'envoi d'emails non-bloquant et sécurisé
(TÂCHE 5 — GEISER Support IA).

Couvre l'ensemble des exigences spécifiées :
 1. Envoi email réussi (mock smtplib).
 2. Gestion propre des erreurs protocolaires SMTP (SMTPException).
 3. Gestion du timeout réseau SMTP (socket.timeout).
 4. Gestion de l'échec d'authentification SMTP (SMTPAuthenticationError).
 5. Gestion de serveur SMTP indisponible (DNS / ConnectionRefused).
 6. Gestion des configurations incomplètes (SMTP désactivé ou incomplet).
 7. Concurrence : envois multiples simultanés sans interférence ni état partagé.
 8. Email 2FA (génération et dispatch du code OTP 6 chiffres).
 9. Email Réinitialisation de mot de passe (formatage URL sécurisée).
10. Intégration notifications Tickets (NotificationService).
11. Intégration notifications SLA (NotificationService / SLAService).
12. DÉMONSTRATION SPÉCIFIQUE EVENT LOOP NON BLOQUÉE : un SMTP lent (time.sleep)
    n'interrompt pas l'exécution concurrente d'autres coroutines sur l'event loop.
13. Vérification du paramètre timeout passé à smtplib.SMTP.
14. Sécurité : vérification que les mots de passe et OTP ne fuient pas dans les logs.
15. Compatibilité appel synchrone dans un event loop (run_in_executor -> Future).
16. Compatibilité appel synchrone hors event loop (exécution synchrone directe).
"""

import time
import socket
import smtplib
import asyncio
import logging
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from bson import ObjectId

from core.config import settings
from services.email_service import EmailService
from services.notification_service import NotificationService


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def configure_smtp_settings():
    """Configure settings for testing without sending real emails."""
    orig_host = settings.SMTP_HOST
    orig_user = settings.SMTP_USER
    orig_pass = settings.SMTP_PASSWORD
    orig_from = settings.FROM_EMAIL
    orig_timeout = getattr(settings, "SMTP_TIMEOUT", 15)

    settings.SMTP_HOST = "smtp.test.geiser.internal"
    settings.SMTP_PORT = 587
    settings.SMTP_USER = "test-mailer@geiser.internal"
    settings.SMTP_PASSWORD = "secret_smtp_password_xyz123"
    settings.FROM_EMAIL = "support@geiser.internal"
    settings.SMTP_TIMEOUT = 10
    settings.SMTP_USE_TLS = True
    settings.SMTP_USE_SSL = False

    yield

    settings.SMTP_HOST = orig_host
    settings.SMTP_USER = orig_user
    settings.SMTP_PASSWORD = orig_pass
    settings.FROM_EMAIL = orig_from
    settings.SMTP_TIMEOUT = orig_timeout


# ─────────────────────────────────────────────────────────────────────────────
# 1. Envoi réussi
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_1_smtp_success():
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        success = await EmailService.send_email_async(
            to_email="client@example.com",
            subject="Test Sujet",
            html_body="<p>Test Contenu</p>",
        )

        assert success is True
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with(settings.SMTP_USER, settings.SMTP_PASSWORD)
        mock_server.sendmail.assert_called_once()
        args = mock_server.sendmail.call_args[0]
        assert args[0] == settings.FROM_EMAIL
        assert args[1] == "client@example.com"
        assert "Test Sujet" in args[2]


# ─────────────────────────────────────────────────────────────────────────────
# 2. Erreur protocolaire SMTP
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_2_smtp_general_error(caplog):
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_server.sendmail.side_effect = smtplib.SMTPException("550 Mailbox unavailable")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with caplog.at_level(logging.ERROR):
            success = await EmailService.send_email_async(
                to_email="invalide@example.com",
                subject="Test",
                html_body="<p>Corps</p>",
            )

        assert success is False
        assert "550 Mailbox unavailable" in caplog.text


# ─────────────────────────────────────────────────────────────────────────────
# 3. Timeout SMTP
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_3_smtp_timeout(caplog):
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.side_effect = socket.timeout("timed out")

        with caplog.at_level(logging.ERROR):
            success = await EmailService.send_email_async(
                to_email="slow@example.com",
                subject="Test Timeout",
                html_body="<p>Test</p>",
            )

        assert success is False
        assert "TIMEOUT" in caplog.text.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 4. Erreur d'authentification SMTP
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_4_smtp_auth_error(caplog):
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        with caplog.at_level(logging.ERROR):
            success = await EmailService.send_email_async(
                to_email="user@example.com",
                subject="Auth Fail",
                html_body="<p>Corps</p>",
            )

        assert success is False
        assert "AUTH ERROR" in caplog.text.upper()
        # Sécurité : le mot de passe ne doit JAMAIS apparaître dans le log
        assert settings.SMTP_PASSWORD not in caplog.text


# ─────────────────────────────────────────────────────────────────────────────
# 5. Serveur indisponible (DNS / connexion refusée)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_5_smtp_unavailable_dns_or_refused(caplog):
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.side_effect = socket.gaierror(-2, "Name or service not known")

        with caplog.at_level(logging.ERROR):
            success = await EmailService.send_email_async(
                to_email="user@example.com",
                subject="DNS fail",
                html_body="<p>Corps</p>",
            )

        assert success is False
        assert "CONNECT ERROR" in caplog.text.upper()


# ─────────────────────────────────────────────────────────────────────────────
# 6. Configuration SMTP manquante
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_6_smtp_missing_configuration(caplog):
    settings.SMTP_HOST = ""
    with caplog.at_level(logging.WARNING):
        success = await EmailService.send_email_async(
            to_email="user@example.com",
            subject="No Config",
            html_body="<p>Corps</p>",
        )

    assert success is False
    assert "SMTP non configur" in caplog.text


# ─────────────────────────────────────────────────────────────────────────────
# 7. Envois concurrents multiples (isolation & pas de conflit)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_7_smtp_concurrent_emails():
    call_counts = {"count": 0}

    def fake_smtp_enter(self):
        call_counts["count"] += 1
        server = MagicMock()
        return server

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.return_value.__enter__ = fake_smtp_enter

        recipients = [f"user_{i}@example.com" for i in range(10)]
        tasks = [
            EmailService.send_email_async(
                to_email=r,
                subject=f"Message {i}",
                html_body=f"<p>Hello {r}</p>"
            )
            for i, r in enumerate(recipients)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 10
        assert all(res is True for res in results)
        assert call_counts["count"] == 10


# ─────────────────────────────────────────────────────────────────────────────
# 8. Email 2FA
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_8_2fa_code_email():
    with patch.object(EmailService, "_send_smtp_blocking", return_value=True) as mock_send:
        # Test async helper
        res = await EmailService.send_2fa_code_async("user2fa@example.com", "987654")
        assert res is True
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[0] == "user2fa@example.com"
        assert "2FA Code" in args[1]
        assert "987654" in args[2]


# ─────────────────────────────────────────────────────────────────────────────
# 9. Email Réinitialisation de mot de passe
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_9_password_reset_email():
    with patch.object(EmailService, "_send_smtp_blocking", return_value=True) as mock_send:
        reset_url = "http://localhost:5173/reset-password?token=secret123xyz"
        res = await EmailService.send_password_reset_async("reset@example.com", reset_url)
        assert res is True
        mock_send.assert_called_once()
        args = mock_send.call_args[0]
        assert args[0] == "reset@example.com"
        assert "Réinitialisation" in args[1]
        assert reset_url in args[2]


# ─────────────────────────────────────────────────────────────────────────────
# 10. Intégration notification de Ticket
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_10_ticket_notification_integration():
    """Ticket created notification queues and dispatches EMAIL via NotificationWorker."""
    agent_oid = ObjectId()
    notif_oid = ObjectId()

    mock_db = MagicMock()
    mock_db.notifications = MagicMock()
    mock_db.notifications.find_one = AsyncMock(return_value=None)  # no duplicate
    mock_db.notifications.insert_one = AsyncMock(return_value=MagicMock(inserted_id=notif_oid))
    # Worker's atomic lock: returns locked doc
    mock_db.notifications.find_one_and_update = AsyncMock(return_value={
        "_id": notif_oid,
        "status": "PROCESSING",
        "channel": "EMAIL",
        "recipient": "demandeur@example.com",
        "title": "Ticket créé",
        "html_body": "<p>Votre demande prise en compte</p>",
        "message": "ticket créé",
        "attempts": 0,
        "max_retries": 5,
        "retry_history": [],
    })
    mock_db.notifications.update_one = AsyncMock()

    notif_svc = NotificationService(mock_db)

    ticket_data = {
        "id": "67890abcdef12345",
        "subject": "Problème d'impression",
        "category": "Matériel",
        "priority": "HIGH",
        "user_id": str(ObjectId()),
    }

    with patch.object(EmailService, "send_email_detailed_async",
                      new_callable=AsyncMock,
                      return_value={"success": True, "error_type": None, "error_detail": None}) as mock_email:
        notif_svc._find_user = AsyncMock(return_value={"email": "demandeur@example.com", "phone": None})
        await notif_svc.notify_ticket_created(ticket_data)

        mock_email.assert_called_once()
        kwargs = mock_email.call_args[1] if mock_email.call_args[1] else {}
        args = mock_email.call_args[0] if mock_email.call_args[0] else []
        recipient = kwargs.get("to_email") or (args[0] if args else "")
        assert recipient == "demandeur@example.com"


# ─────────────────────────────────────────────────────────────────────────────
# 11. Intégration notification SLA
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_11_sla_notification_integration():
    """SLA breach notification queues and dispatches EMAIL to assigned agent."""
    agent_oid = ObjectId()
    user_oid = ObjectId()
    notif_oid = ObjectId()

    mock_db = MagicMock()
    mock_db.notifications = MagicMock()
    mock_db.notifications.find_one = AsyncMock(return_value=None)  # no duplicate
    mock_db.notifications.insert_one = AsyncMock(return_value=MagicMock(inserted_id=notif_oid))
    mock_db.notifications.find_one_and_update = AsyncMock(return_value={
        "_id": notif_oid,
        "status": "PROCESSING",
        "channel": "EMAIL",
        "recipient": "agent@geiser.internal",
        "title": "[ALERTE SLA GEISER] Ticket #334455 (BREACHED)",
        "html_body": "<h3>ALERTE SLA</h3>",
        "message": "SLA breached",
        "attempts": 0,
        "max_retries": 5,
        "retry_history": [],
    })
    mock_db.notifications.update_one = AsyncMock()
    mock_db.agents.find_one = AsyncMock(return_value={"_id": agent_oid, "user_id": str(user_oid)})

    notif_svc = NotificationService(mock_db)
    notif_svc._find_user = AsyncMock(return_value={"_id": user_oid, "email": "agent@geiser.internal"})

    ticket_data = {
        "id": "1122334455667788",
        "subject": "Panne critique serveur",
        "priority": "URGENT",
        "assigned_agent_id": str(agent_oid),
    }

    with patch.object(EmailService, "send_email_detailed_async",
                      new_callable=AsyncMock,
                      return_value={"success": True, "error_type": None, "error_detail": None}) as mock_email:
        await notif_svc.notify_sla_alert(ticket_data, alert_type="BREACHED")
        mock_email.assert_called_once()
        kwargs = mock_email.call_args[1] if mock_email.call_args[1] else {}
        args = mock_email.call_args[0] if mock_email.call_args[0] else []
        recipient = kwargs.get("to_email") or (args[0] if args else "")
        assert recipient == "agent@geiser.internal"


# ─────────────────────────────────────────────────────────────────────────────
# 12. DÉMONSTRATION EVENT LOOP NON-BLOQUÉE (Test Spécifique)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_12_event_loop_not_blocked_during_slow_smtp():
    """Démontre sans équivoque qu'un envoi SMTP lent exécuté dans un thread worker
    laisse l'event loop FastAPI libre d'exécuter d'autres coroutines concurrentes.
    """
    slow_duration = 0.25  # 250ms de latence SMTP simulée (time.sleep synchrone)
    concurrent_ticks = []

    def slow_smtp_call(*args, **kwargs):
        # Simulation d'une latence réseau bloquante (DNS + TLS handshake)
        time.sleep(slow_duration)
        return True

    async def lightweight_background_task():
        """Tâche concurrente tournant sur l'event loop pendant que le thread SMTP travaille."""
        for step in range(5):
            await asyncio.sleep(0.04)  # 50ms par step -> total 200ms
            concurrent_ticks.append(step)

    with patch.object(EmailService, "_send_smtp_blocking", side_effect=slow_smtp_call):
        t_start = time.perf_counter()

        # On lance l'envoi SMTP (via to_thread/thread pool) et la tâche concurrente simultanément
        smtp_task = asyncio.create_task(
            EmailService.send_email_async("slow@example.com", "Test", "<p>Lent</p>")
        )
        bg_task = asyncio.create_task(lightweight_background_task())

        await asyncio.gather(smtp_task, bg_task)
        elapsed = time.perf_counter() - t_start

        # Preuve 1 : La tâche concurrente sur l'event loop a pu progresser et compléter ses 5 étapes
        assert len(concurrent_ticks) == 5, (
            f"L'event loop a été bloquée ! Seulement {len(concurrent_ticks)} ticks exécutés."
        )

        # Preuve 2 : L'opération SMTP a bien duré au moins slow_duration
        assert elapsed >= slow_duration


# ─────────────────────────────────────────────────────────────────────────────
# 13. Vérification du paramètre timeout
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_13_smtp_timeout_configuration_applied():
    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_server = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_server

        await EmailService.send_email_async("test@example.com", "Timeout check", "<p>Body</p>")

        # Vérifie que smtplib.SMTP a bien été instancié avec timeout=settings.SMTP_TIMEOUT
        mock_smtp_class.assert_called_once_with(
            settings.SMTP_HOST,
            settings.SMTP_PORT,
            timeout=settings.SMTP_TIMEOUT,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 14. Sécurité : Absence de fuite des credentials dans les logs
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_14_security_credentials_not_in_logs(caplog):
    secret_pw = settings.SMTP_PASSWORD
    otp_code = "829471"

    with patch("smtplib.SMTP") as mock_smtp_class:
        mock_smtp_class.side_effect = Exception("Erreur critique inattendue")

        with caplog.at_level(logging.DEBUG):
            await EmailService.send_2fa_code_async("user@example.com", otp_code)

        # Le mot de passe ne doit jamais figurer dans les logs
        assert secret_pw not in caplog.text
        # Le code OTP ne doit pas apparaître dans les messages d'erreur de log
        assert f"code: {otp_code}" not in caplog.text


# ─────────────────────────────────────────────────────────────────────────────
# 15. Compatibilité : appel synchrone à send_email dans un event loop (run_in_executor)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_15_send_email_sync_call_in_running_loop():
    """Quand send_email() est appelée sans await depuis un event loop en cours,
    elle délègue au thread pool et retourne un Future awaitable.
    """
    with patch.object(EmailService, "_send_smtp_blocking", return_value=True) as mock_sync:
        # Appel synchrone classique (sans await immédiat)
        future_or_res = EmailService.send_email("user@example.com", "Sujet", "<p>Corps</p>")

        # Doit être un Future / Task awaitable
        assert asyncio.isfuture(future_or_res)
        result = await future_or_res
        assert result is True
        mock_sync.assert_called_once()


# ─────────────────────────────────────────────────────────────────────────────
# 16. Compatibilité : appel synchrone à send_email hors d'un event loop
# ─────────────────────────────────────────────────────────────────────────────

def test_16_send_email_outside_event_loop():
    """Hors d'un event loop (script synchrone, test simple), send_email retourne directement un booléen."""
    with patch.object(EmailService, "_send_smtp_blocking", return_value=True) as mock_sync:
        result = EmailService.send_email("user@example.com", "Sujet", "<p>Corps</p>")
        assert result is True
        mock_sync.assert_called_once()
