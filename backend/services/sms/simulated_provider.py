import logging
import uuid
from typing import Optional

from services.sms.sms_provider import SMSProvider, SMSResult
from services.sms.twilio_provider import validate_e164_phone

logger = logging.getLogger(__name__)


class SimulatedSMSProvider(SMSProvider):
    """
    Simulated SMS Provider for GEISER Helpdesk.
    Used in local development, testing, or when Twilio credentials are not configured.
    Logs dispatch and generates a deterministic simulated message ID.
    """

    @property
    def provider_name(self) -> str:
        return "simulated"

    def is_configured(self) -> bool:
        return True

    async def send_sms(self, to: str, message: str) -> SMSResult:
        normalized_to = validate_e164_phone(to) or to
        if not message or not message.strip():
            return SMSResult(
                success=False,
                status="failed",
                provider=self.provider_name,
                to=normalized_to,
                error="SMS message body cannot be empty"
            )

        sim_id = f"SIM-{uuid.uuid4().hex[:12].upper()}"
        logger.info(f"[SIMULATED SMS] To: {normalized_to} | ID: {sim_id} | Body: {message}")
        return SMSResult(
            success=True,
            status="simulated",
            provider=self.provider_name,
            message_id=sim_id,
            to=normalized_to,
            error=None
        )
