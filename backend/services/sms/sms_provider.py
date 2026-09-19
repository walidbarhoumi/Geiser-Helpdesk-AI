from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class SMSResult:
    success: bool
    message_id: Optional[str] = None
    status: str = "sent"  # sent, failed, simulated, skipped_duplicate
    provider: str = "unknown"
    to: Optional[str] = None
    error: Optional[str] = None


class SMSProvider(ABC):
    """Abstract base class for all SMS providers (Twilio, Simulated, etc.)."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Returns the identifier name of the provider."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Checks if required credentials/configurations are present."""
        pass

    @abstractmethod
    async def send_sms(self, to: str, message: str) -> SMSResult:
        """
        Sends an SMS to the destination number.
        Must never raise unhandled exceptions or leak secrets.
        """
        pass
