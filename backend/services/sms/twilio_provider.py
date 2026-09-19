import asyncio
import logging
import re
from typing import Optional

from core.config import settings
from services.sms.sms_provider import SMSProvider, SMSResult

logger = logging.getLogger(__name__)

# International E.164 pattern: + followed by 1-15 digits
E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


def validate_e164_phone(phone: Optional[str]) -> Optional[str]:
    """
    Validates and normalizes phone number to E.164 format.
    Strips spaces, dots, dashes, parentheses.
    Returns normalized string if valid, None otherwise.
    """
    if not phone or not isinstance(phone, str):
        return None
    cleaned = re.sub(r"[\s\-\.\(\)]", "", phone.strip())
    if E164_REGEX.match(cleaned):
        return cleaned
    return None


class TwilioProvider(SMSProvider):
    """
    Official Twilio SMS Provider for GEISER Helpdesk.
    Sends SMS using Twilio REST API via credentials stored in environment/settings.
    Guarantees strict security: credentials are never logged or exposed in errors.
    """

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
        client: Optional[any] = None,
    ):
        self._account_sid = account_sid or getattr(settings, "TWILIO_ACCOUNT_SID", "")
        self._auth_token = auth_token or getattr(settings, "TWILIO_AUTH_TOKEN", "")
        self._from_number = from_number or getattr(settings, "TWILIO_FROM_NUMBER", "")
        self._client = client

    @property
    def provider_name(self) -> str:
        return "twilio"

    def is_configured(self) -> bool:
        """Returns True if all required Twilio credentials are set."""
        return bool(self._account_sid and self._auth_token and self._from_number)

    def _get_client(self):
        """Initializes and returns a Twilio Client instance."""
        if self._client is not None:
            return self._client
        if not self.is_configured():
            raise ValueError("Twilio credentials not configured")
        from twilio.rest import Client
        return Client(self._account_sid, self._auth_token)

    def _sanitize_error_message(self, err_msg: str) -> str:
        """Strips any potential credentials from error messages."""
        if not err_msg:
            return "Twilio API error"
        sanitized = err_msg
        if self._auth_token and len(self._auth_token) > 4:
            sanitized = sanitized.replace(self._auth_token, "[REDACTED]")
        if self._account_sid and len(self._account_sid) > 4:
            sanitized = sanitized.replace(self._account_sid, "[REDACTED_SID]")
        return sanitized

    async def send_sms(self, to: str, message: str) -> SMSResult:
        """
        Sends an SMS message to a validated E.164 phone number.
        Returns SMSResult with success=True and Twilio SID on success.
        Gracefully handles invalid numbers, missing credentials, and API errors.
        """
        # 1. Validation du numéro destinataire
        normalized_to = validate_e164_phone(to)
        if not normalized_to:
            logger.warning(f"[TWILIO SMS] Invalid destination phone number: '{to}'")
            return SMSResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                to=to,
                error=f"Invalid destination phone number format (expected E.164, e.g. +33612345678, received: '{to}')"
            )

        # 2. Validation du contenu du message
        if not message or not message.strip():
            return SMSResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                to=normalized_to,
                error="SMS message body cannot be empty"
            )

        # 3. Vérification des credentials
        if not self.is_configured():
            logger.warning("[TWILIO SMS] Twilio credentials missing in configuration")
            return SMSResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                to=normalized_to,
                error="Twilio credentials not configured (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN or TWILIO_FROM_NUMBER missing)"
            )

        # 4. Envoi via Twilio dans un thread non-bloquant
        def _sync_send():
            client = self._get_client()
            return client.messages.create(
                to=normalized_to,
                from_=self._from_number,
                body=message.strip()
            )

        try:
            twilio_msg = await asyncio.to_thread(_sync_send)
            message_sid = getattr(twilio_msg, "sid", None) or str(twilio_msg)
            logger.info(f"[TWILIO SMS] Sent successfully to {normalized_to} (SID: {message_sid})")
            return SMSResult(
                success=True,
                status="sent",
                provider=self.provider_name,
                message_id=message_sid,
                to=normalized_to,
                error=None
            )
        except Exception as exc:
            from twilio.base.exceptions import TwilioRestException
            raw_err = str(exc)
            safe_err = self._sanitize_error_message(raw_err)
            if isinstance(exc, TwilioRestException):
                logger.error(f"[TWILIO SMS] TwilioRestException code={exc.code} status={exc.status}: {safe_err}")
                return SMSResult(
                    success=False,
                    status="failed",
                    provider=self.provider_name,
                    to=normalized_to,
                    error=f"Twilio error (code {exc.code}): {safe_err}"
                )
            logger.error(f"[TWILIO SMS] Dispatch error to {normalized_to}: {safe_err}")
            return SMSResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                to=normalized_to,
                error=safe_err
            )
