import httpx
import json
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class OllamaService:
    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = settings.OLLAMA_MODEL

    async def generate_response(self, prompt: str, system_prompt: str = "") -> str:
        """
        Generates text using Ollama.
        """
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": self.model,
                        "prompt": prompt,
                        "system": system_prompt,
                        "stream": False,
                        "options": {
                            "temperature": 0.3,
                            "top_p": 0.9
                        }
                    }
                )
                if response.status_code == 200:
                    return response.json().get("response", "").strip()
                return ""
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            return ""

    async def generate_json(self, prompt: str, system_prompt: str = "") -> dict:
        """
        Generates structured JSON using Ollama.

        Error handling:
        - raw_response is always initialized to None before the try block so that
          the except clause can safely reference it even if generate_response() raises.
        - An empty or None response is caught explicitly before json.loads() to avoid
          a secondary JSONDecodeError with an unhelpful empty-string message.
        - Raw content is truncated in logs to avoid leaking sensitive ticket data.
        - Returns {} on any failure so callers fall back to their heuristic path.
        """
        raw_response: str | None = None   # always defined — guards UnboundLocalError
        try:
            # Enforce JSON output via system prompt
            full_system = (
                f"{system_prompt}\n"
                "Return ONLY a valid JSON object. No preamble, no markdown blocks."
            )

            raw_response = await self.generate_response(prompt, full_system)

            if not raw_response:
                logger.warning("Ollama returned an empty response for a JSON request.")
                return {}

            # Strip possible markdown fences before parsing
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()

            if not clean_json:
                logger.warning("Ollama response was non-empty but contained only markdown fences.")
                return {}

            return json.loads(clean_json)

        except json.JSONDecodeError as exc:
            # Truncate raw content to 500 chars — avoids leaking ticket descriptions in logs
            preview = (raw_response or "")[:500]
            logger.error(
                "Ollama JSON parsing error: %s | raw preview (500 chars): %r",
                exc,
                preview,
            )
            return {}

        except Exception as exc:
            # Unexpected error (network, timeout, etc.) — raw_response may still be None
            preview = (raw_response or "")[:500] if raw_response else "<not received>"
            logger.error(
                "Ollama generate_json unexpected error: %s | raw preview: %r",
                exc,
                preview,
            )
            return {}

