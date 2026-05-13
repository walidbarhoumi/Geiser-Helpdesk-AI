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
        """
        try:
            # We enforce JSON in the system prompt for better reliability
            full_system = f"{system_prompt}\nReturn ONLY a valid JSON object. No preamble, no markdown blocks."
            
            raw_response = await self.generate_response(prompt, full_system)
            
            # Clean possible markdown blocks
            clean_json = raw_response.replace("```json", "").replace("```", "").strip()
            return json.loads(clean_json)
        except Exception as e:
            logger.error(f"Ollama JSON parsing error: {e}. Raw: {raw_response}")
            return {}
