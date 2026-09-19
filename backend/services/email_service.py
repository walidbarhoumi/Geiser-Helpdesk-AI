import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from core.config import settings
import logging

logger = logging.getLogger(__name__)

class EmailService:
    @staticmethod
    def send_email(to_email: str, subject: str, html_body: str):
        if not settings.SMTP_HOST or not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.warning(f"SMTP not configured. Skipping email to {to_email}. Content:\n{html_body}")
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email

        part = MIMEText(html_body, "html")
        msg.attach(part)

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.FROM_EMAIL, to_email, msg.as_string())
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    @staticmethod
    def send_2fa_code(to_email: str, code: str):
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
        return EmailService.send_email(to_email, subject, body)

    @staticmethod
    def send_password_reset(to_email: str, reset_url: str):
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
        return EmailService.send_email(to_email, subject, body)

