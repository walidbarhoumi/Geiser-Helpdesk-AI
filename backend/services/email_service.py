"""
email_service.py
==============================================================================
Service d'envoi d'emails non-bloquant pour GEISER Support IA.

Architecture & Résolution du blocage de l'Event Loop :
- Les appels SMTP réseau (DNS, socket connect, TLS, auth, sendmail) sont
  exécutés hors de l'event loop FastAPI via un thread pool dédié (`ThreadPoolExecutor`).
- Deux modes d'accès sont supportés :
  1. `send_email_async` : méthode `async` retournant une coroutine (awaitable),
     utilisant `asyncio.to_thread` pour un envoi non-bloquant avec attente du résultat.
  2. `send_email` : méthode universelle compatible rétroactivement :
     - Si appelée depuis un event loop en cours d'exécution, elle soumet l'envoi au
       pool de threads via `loop.run_in_executor` et retourne un `asyncio.Future`
       (qui peut être attendu avec `await` ou exécuté en arrière-plan sans bloquer).
     - Si appelée hors event loop (scripts synchrones, tests unitaires), elle s'exécute
       de façon synchrone directe.
- Gestion robuste des timeouts via `settings.SMTP_TIMEOUT` (défaut : 15s).
- Isolation totale des connexions SMTP par opération : chaque appel instancie son propre
  client SMTP, évitant tout partage d'état mutable entre threads ou requêtes concurrentes.
- Sécurité renforcée : aucun mot de passe, token ou code OTP n'est consigné dans les logs.
"""

import smtplib
import socket
import ssl
import asyncio
from concurrent.futures import ThreadPoolExecutor
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import Optional, List, Dict, Any
from core.config import settings
import logging

logger = logging.getLogger(__name__)

# Dedicated thread pool for SMTP network I/O offloaded from the event loop
_smtp_executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="smtp-worker")


class EmailService:
    """Service d'envoi d'emails sécurisé et non-bloquant."""

    # -------------------------------------------------------------------------
    # Construction du message MIME
    # -------------------------------------------------------------------------

    @staticmethod
    def _build_message(
        to_email: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> MIMEMultipart:
        """Construit un objet MIMEMultipart avec corps HTML et pièces jointes éventuelles."""
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email

        # Alternative part for HTML body
        body_part = MIMEText(html_body, "html", "utf-8")
        msg.attach(body_part)

        # Optional attachments: list of dicts with {"filename": str, "content": bytes, "mime_type": str}
        if attachments:
            for att in attachments:
                try:
                    filename = att.get("filename", "attachment")
                    content = att.get("content", b"")
                    mime_type = att.get("mime_type", "application/octet-stream")
                    maintype, _, subtype = mime_type.partition("/")
                    part = MIMEBase(maintype or "application", subtype or "octet-stream")
                    part.set_payload(content)
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename="{filename}"'
                    )
                    msg.attach(part)
                except Exception as att_err:
                    logger.warning(f"Could not attach file {att.get('filename')}: {att_err}")

        return msg

    # -------------------------------------------------------------------------
    # Envoi SMTP synchrone (exécuté dans un worker thread dédié)
    # -------------------------------------------------------------------------

    @classmethod
    def _send_smtp_detailed_blocking(
        cls,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Exécute l'envoi SMTP et classe les erreurs en TEMPORARY vs PERMANENT."""
        if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(
                f"[SMTP] SMTP non configuré (hôte ou identifiants manquants). "
                f"Envoi ignoré vers : {to_email} ('{subject}')"
            )
            return {
                "success": False,
                "error_type": "PERMANENT",
                "error_detail": "SMTP credentials not configured"
            }

        if not to_email or "@" not in str(to_email):
            logger.error(f"[SMTP] Adresse destinataire invalide : {to_email}")
            return {
                "success": False,
                "error_type": "PERMANENT",
                "error_detail": f"Invalid recipient email syntax: {to_email}"
            }

        msg = cls._build_message(to_email, subject, html_body, attachments)
        timeout = getattr(settings, "SMTP_TIMEOUT", 15)

        try:
            if getattr(settings, "SMTP_USE_SSL", False):
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(
                    settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=timeout
                ) as server:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())
            else:
                with smtplib.SMTP(
                    settings.SMTP_HOST, settings.SMTP_PORT, timeout=timeout
                ) as server:
                    if getattr(settings, "SMTP_USE_TLS", True):
                        server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())

            logger.info(f"[SMTP] Email envoyé avec succès à {to_email} ('{subject}')")
            return {"success": True, "error_type": None, "error_detail": None}

        except smtplib.SMTPAuthenticationError as auth_err:
            logger.error(
                f"[SMTP AUTH ERROR] Échec de l'authentification SMTP pour l'utilisateur "
                f"'{settings.SMTP_USER}' sur {settings.SMTP_HOST}:{settings.SMTP_PORT}."
            )
            return {
                "success": False,
                "error_type": "PERMANENT",
                "error_detail": f"SMTP Authentication failed: {auth_err}"
            }

        except smtplib.SMTPRecipientsRefused as rec_err:
            logger.error(f"[SMTP RECIPIENT ERROR] Destinataire refusé : {rec_err}")
            return {
                "success": False,
                "error_type": "PERMANENT",
                "error_detail": f"Recipient refused: {rec_err}"
            }

        except smtplib.SMTPSenderRefused as send_err:
            logger.error(f"[SMTP SENDER ERROR] Expéditeur refusé : {send_err}")
            return {
                "success": False,
                "error_type": "PERMANENT",
                "error_detail": f"Sender refused: {send_err}"
            }

        except (socket.timeout, TimeoutError) as to_err:
            logger.error(
                f"[SMTP TIMEOUT] Délai d'attente dépassé ({timeout}s) lors de la communication "
                f"avec le serveur SMTP {settings.SMTP_HOST}:{settings.SMTP_PORT} pour {to_email}."
            )
            return {
                "success": False,
                "error_type": "TEMPORARY",
                "error_detail": f"Connection timeout ({timeout}s): {to_err}"
            }

        except (socket.gaierror, ConnectionRefusedError, smtplib.SMTPConnectError) as conn_err:
            logger.error(
                f"[SMTP CONNECT ERROR] Impossible d'établir la connexion avec le serveur SMTP "
                f"{settings.SMTP_HOST}:{settings.SMTP_PORT} : {conn_err}"
            )
            return {
                "success": False,
                "error_type": "TEMPORARY",
                "error_detail": f"SMTP connection error: {conn_err}"
            }

        except smtplib.SMTPServerDisconnected as disc_err:
            logger.error(
                f"[SMTP DISCONNECT] Le serveur SMTP distant a fermé la connexion de façon inattendue : {disc_err}"
            )
            return {
                "success": False,
                "error_type": "TEMPORARY",
                "error_detail": f"Server disconnected unexpectedly: {disc_err}"
            }

        except smtplib.SMTPDataError as data_err:
            code = getattr(data_err, "smtp_code", 500)
            err_type = "PERMANENT" if code >= 500 else "TEMPORARY"
            logger.error(f"[SMTP DATA ERROR] {data_err} (code={code})")
            return {
                "success": False,
                "error_type": err_type,
                "error_detail": f"SMTP data error ({code}): {data_err}"
            }

        except smtplib.SMTPException as smtp_err:
            logger.error(
                f"[SMTP ERROR] Erreur protocolaire SMTP lors de l'envoi à {to_email} : {smtp_err}"
            )
            return {
                "success": False,
                "error_type": "TEMPORARY",
                "error_detail": f"SMTP protocol error: {smtp_err}"
            }

        except Exception as exc:
            logger.error(
                f"[SMTP UNEXPECTED] Erreur inattendue lors de l'envoi à {to_email} : {exc}"
            )
            return {
                "success": False,
                "error_type": "TEMPORARY",
                "error_detail": f"Unexpected error: {type(exc).__name__} - {exc}"
            }

    @classmethod
    def _send_smtp_blocking(
        cls,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Exécute l'opération réseau SMTP de manière synchrone et isolée."""
        res = cls._send_smtp_detailed_blocking(to_email, subject, html_body, attachments)
        return bool(res.get("success", False))

    # -------------------------------------------------------------------------
    # API Asynchrone Pure (asyncio.to_thread)
    # -------------------------------------------------------------------------

    @classmethod
    async def send_email_async(
        cls,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        """Envoie un email de manière asynchrone sans bloquer l'event loop FastAPI.
        Exécute la communication SMTP dans un worker thread dédié via `asyncio.to_thread`.
        """
        return await asyncio.to_thread(
            cls._send_smtp_blocking, to_email, subject, html_body, attachments
        )

    @classmethod
    async def send_email_detailed_async(
        cls,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Envoie un email et retourne un dictionnaire détaillé du résultat et de l'erreur."""
        return await asyncio.to_thread(
            cls._send_smtp_detailed_blocking, to_email, subject, html_body, attachments
        )

    # -------------------------------------------------------------------------
    # API Universelle Non-Bloquante (rétrocompatible avec tous les appelants existants)
    # -------------------------------------------------------------------------

    @classmethod
    def send_email(
        cls,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: Optional[List[Dict[str, Any]]] = None,
    ):
        """Distribue l'envoi d'email sans bloquer l'event loop FastAPI.

        - Dans le contexte d'un event loop en cours d'exécution (FastAPI async routes/services) :
          l'envoi est automatiquement déporté dans le thread pool via `loop.run_in_executor`.
          Retourne un `asyncio.Future` (qui peut être attendu avec `await` ou exécuté
          en arrière-plan en mode non-bloquant).
        - Hors d'un event loop (scripts standalone, tests synchrones) :
          l'envoi s'exécute directement et retourne un booléen `True/False`.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            return loop.run_in_executor(
                _smtp_executor,
                cls._send_smtp_blocking,
                to_email,
                subject,
                html_body,
                attachments,
            )
        return cls._send_smtp_blocking(to_email, subject, html_body, attachments)

    # -------------------------------------------------------------------------
    # Templates & Helpers Dédiés
    # -------------------------------------------------------------------------

    @classmethod
    def send_2fa_code(cls, to_email: str, code: str):
        """Envoi non-bloquant du code d'authentification 2FA."""
        subject = "Your Geiser Helpdesk 2FA Code"
        body = f"""
        <html>
            <body>
                <h2>Geiser Helpdesk Verification</h2>
                <p>Your two-factor authentication code is:</p>
                <h1 style="color: #6366f1; letter-spacing: 2px;">{code}</h1>
                <p>This code will expire in 10 minutes.</p>
                <p>If you did not request this, please ignore this email.</p>
            </body>
        </html>
        """
        return cls.send_email(to_email, subject, body)

    @classmethod
    async def send_2fa_code_async(cls, to_email: str, code: str) -> bool:
        """Envoi asynchrone explicite du code 2FA."""
        subject = "Your Geiser Helpdesk 2FA Code"
        body = f"""
        <html>
            <body>
                <h2>Geiser Helpdesk Verification</h2>
                <p>Your two-factor authentication code is:</p>
                <h1 style="color: #6366f1; letter-spacing: 2px;">{code}</h1>
                <p>This code will expire in 10 minutes.</p>
                <p>If you did not request this, please ignore this email.</p>
            </body>
        </html>
        """
        return await cls.send_email_async(to_email, subject, body)

    @classmethod
    def send_password_reset(cls, to_email: str, reset_url: str):
        """Envoi non-bloquant du lien de réinitialisation de mot de passe."""
        subject = "GEISER Support IA — Réinitialisation de votre mot de passe"
        body = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
          <meta charset="UTF-8">
          <style>
            body {{ font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #080812; margin: 0; padding: 24px; color: #f8fafc; }}
            .container {{ max-width: 540px; margin: 0 auto; background: #0f172a; border-radius: 16px; border: 1px solid rgba(139, 92, 246, 0.2); overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,0.6); }}
            .header {{ background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%); padding: 32px 36px 24px; border-bottom: 1px solid rgba(139, 92, 246, 0.15); }}
            .brand {{ font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.3px; }}
            .brand-accent {{ color: #a78bfa; font-weight: 600; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; margin-top: 4px; }}
            .content {{ padding: 36px; }}
            .title {{ font-size: 22px; font-weight: 700; color: #ffffff; margin-top: 0; margin-bottom: 14px; }}
            .desc {{ font-size: 14.5px; line-height: 1.65; color: #cbd5e1; margin-bottom: 24px; }}
            .button-wrap {{ text-align: center; margin: 32px 0; }}
            .btn {{ display: inline-block; background: linear-gradient(135deg, #7c3aed, #4f46e5); color: #ffffff !important; text-decoration: none; font-weight: 600; font-size: 14.5px; padding: 14px 32px; border-radius: 10px; box-shadow: 0 4px 18px rgba(124, 58, 237, 0.45); }}
            .note {{ font-size: 13px; color: #94a3b8; line-height: 1.55; margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 18px; }}
            .footer {{ background: #0b0f19; padding: 20px 36px; text-align: center; font-size: 11.5px; color: #64748b; border-top: 1px solid rgba(255,255,255,0.05); }}
            .url-box {{ word-break: break-all; font-family: monospace; font-size: 12px; color: #a78bfa; background: rgba(139, 92, 246, 0.08); padding: 10px; border-radius: 6px; border: 1px solid rgba(139, 92, 246, 0.15); margin-top: 10px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <div class="brand">Geiser Support IA</div>
              <div class="brand-accent">Système d'authentification sécurisé</div>
            </div>
            <div class="content">
              <h2 class="title">Demande de réinitialisation</h2>
              <p class="desc">
                Nous avons reçu une demande de réinitialisation de mot de passe pour votre compte <strong>{to_email}</strong>.
              </p>
              <div class="button-wrap">
                <a href="{reset_url}" target="_blank" class="btn">Réinitialiser mon mot de passe</a>
              </div>
              <p class="desc" style="font-size: 13px; color: #94a3b8;">
                Si le bouton ci-dessus ne fonctionne pas, copiez et collez ce lien sécurisé dans votre navigateur :
              </p>
              <div class="url-box">{reset_url}</div>
              <div class="note">
                ⏱️ Ce lien est à usage unique et expire dans <strong>{settings.RESET_TOKEN_EXPIRE_MINUTES} minutes</strong>.<br><br>
                🛡️ Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail en toute sérénité. Votre mot de passe reste inchangé et sécurisé.
              </div>
            </div>
            <div class="footer">
              GEISER AI Workspace · Plateforme ITSM & RAG certifiée ISO/IEC 27001
            </div>
          </div>
        </body>
        </html>
        """
        return cls.send_email(to_email, subject, body)

    @classmethod
    async def send_password_reset_async(cls, to_email: str, reset_url: str) -> bool:
        """Envoi asynchrone explicite du lien de réinitialisation de mot de passe."""
        subject = "GEISER Support IA — Réinitialisation de votre mot de passe"
        body = f"""
        <!DOCTYPE html>
        <html lang="fr">
        <head>
          <meta charset="UTF-8">
          <style>
            body {{ font-family: 'DM Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #080812; margin: 0; padding: 24px; color: #f8fafc; }}
            .container {{ max-width: 540px; margin: 0 auto; background: #0f172a; border-radius: 16px; border: 1px solid rgba(139, 92, 246, 0.2); overflow: hidden; box-shadow: 0 12px 40px rgba(0,0,0,0.6); }}
            .header {{ background: linear-gradient(135deg, #1e1b4b 0%, #0f172a 100%); padding: 32px 36px 24px; border-bottom: 1px solid rgba(139, 92, 246, 0.15); }}
            .brand {{ font-size: 20px; font-weight: 700; color: #ffffff; letter-spacing: -0.3px; }}
            .brand-accent {{ color: #a78bfa; font-weight: 600; font-size: 11px; letter-spacing: 1.5px; text-transform: uppercase; margin-top: 4px; }}
            .content {{ padding: 36px; }}
            .title {{ font-size: 22px; font-weight: 700; color: #ffffff; margin-top: 0; margin-bottom: 14px; }}
            .desc {{ font-size: 14.5px; line-height: 1.65; color: #cbd5e1; margin-bottom: 24px; }}
            .button-wrap {{ text-align: center; margin: 32px 0; }}
            .btn {{ display: inline-block; background: linear-gradient(135deg, #7c3aed, #4f46e5); color: #ffffff !important; text-decoration: none; font-weight: 600; font-size: 14.5px; padding: 14px 32px; border-radius: 10px; box-shadow: 0 4px 18px rgba(124, 58, 237, 0.45); }}
            .note {{ font-size: 13px; color: #94a3b8; line-height: 1.55; margin-top: 24px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 18px; }}
            .footer {{ background: #0b0f19; padding: 20px 36px; text-align: center; font-size: 11.5px; color: #64748b; border-top: 1px solid rgba(255,255,255,0.05); }}
            .url-box {{ word-break: break-all; font-family: monospace; font-size: 12px; color: #a78bfa; background: rgba(139, 92, 246, 0.08); padding: 10px; border-radius: 6px; border: 1px solid rgba(139, 92, 246, 0.15); margin-top: 10px; }}
          </style>
        </head>
        <body>
          <div class="container">
            <div class="header">
              <div class="brand">Geiser Support IA</div>
              <div class="brand-accent">Système d'authentification sécurisé</div>
            </div>
            <div class="content">
              <h2 class="title">Demande de réinitialisation</h2>
              <p class="desc">
                Nous avons reçu une demande de réinitialisation de mot de passe pour votre compte <strong>{to_email}</strong>.
              </p>
              <div class="button-wrap">
                <a href="{reset_url}" target="_blank" class="btn">Réinitialiser mon mot de passe</a>
              </div>
              <p class="desc" style="font-size: 13px; color: #94a3b8;">
                Si le bouton ci-dessus ne fonctionne pas, copiez et collez ce lien sécurisé dans votre navigateur :
              </p>
              <div class="url-box">{reset_url}</div>
              <div class="note">
                ⏱️ Ce lien est à usage unique et expire dans <strong>{settings.RESET_TOKEN_EXPIRE_MINUTES} minutes</strong>.<br><br>
                🛡️ Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail en toute sérénité. Votre mot de passe reste inchangé et sécurisé.
              </div>
            </div>
            <div class="footer">
              GEISER AI Workspace · Plateforme ITSM & RAG certifiée ISO/IEC 27001
            </div>
          </div>
        </body>
        </html>
        """
        return await cls.send_email_async(to_email, subject, body)
