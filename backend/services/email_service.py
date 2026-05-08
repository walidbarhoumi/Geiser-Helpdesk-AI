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
        subject = "Reset Your Geiser Helpdesk Password"
        body = f"""
        <html>
            <body>
                <h2>Password Reset Request</h2>
                <p>We received a request to reset your password.</p>
                <p>Click the link below to set a new password:</p>
                <a href="{reset_url}" style="display: inline-block; padding: 10px 20px; background-color: #6366f1; color: white; text-decoration: none; border-radius: 5px;">Reset Password</a>
                <p>If you cannot click the button, copy and paste this link into your browser:</p>
                <p>{reset_url}</p>
                <p>This link will expire in 15 minutes.</p>
                <p>If you did not request this, please ignore this email.</p>
            </body>
        </html>
        """
        return EmailService.send_email(to_email, subject, body)
