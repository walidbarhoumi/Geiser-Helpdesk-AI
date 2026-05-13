import httpx
import json
import logging
from core.config import settings

logger = logging.getLogger(__name__)

class OllamaClient:
    def __init__(self):
        self.base_url = settings.OLLAMA_URL
        self.model = settings.OLLAMA_MODEL

    async def generate_response(self, prompt: str, system_prompt: str = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("response", "")
        except Exception as e:
            logger.error(f"Error calling Ollama API: {e}")
            return ""

    async def analyze_ticket(self, ticket_data: dict) -> dict:
        """
        Uses Ollama to analyze the ticket and extract key skills/intent.
        Returns a JSON-like dictionary.
        """
        system_prompt = (
            "You are an ITSM AI expert. Analyze the helpdesk ticket and output ONLY a JSON object "
            "with 'keywords' (list of technical skills), 'category_suggestion', and 'urgency_score' (1-10)."
        )
        prompt = (
            f"Subject: {ticket_data.get('subject')}\n"
            f"Description: {ticket_data.get('description')}\n"
            f"Category: {ticket_data.get('category')}\n"
            f"Subcategory: {ticket_data.get('subcategory')}"
        )

        response_text = await self.generate_response(prompt, system_prompt)
        
        # Simple extraction of JSON from response
        try:
            # Look for the first { and last }
            start = response_text.find("{")
            end = response_text.rfind("}") + 1
            if start != -1 and end != 0:
                json_str = response_text[start:end]
                return json.loads(json_str)
        except Exception as e:
            logger.warning(f"Failed to parse AI response as JSON: {e}")
            
        return {"keywords": [], "category_suggestion": "", "urgency_score": 5}

    async def check_health(self) -> dict:
        """
        Verifies if Ollama is reachable and the model is available.
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Check tags to see if model is loaded
                response = await client.get(f"{self.base_url}/api/tags")
                if response.status_code == 200:
                    models = response.json().get("models", [])
                    model_names = [m.get("name") for m in models]
                    is_loaded = any(self.model in name for name in model_names)
                    
                    # Check hardware info from /api/ps
                    hardware_info = "Unknown"
                    try:
                        ps_res = await client.get(f"{self.base_url}/api/ps")
                        if ps_res.status_code == 200:
                            running_models = ps_res.json().get("models", [])
                            for m in running_models:
                                if self.model in m.get("name", ""):
                                    # If size_vram > 0, it's likely using GPU
                                    vram = m.get("size_vram", 0)
                                    hardware_info = "GPU" if vram > 0 else "CPU"
                    except:
                        pass

                    return {
                        "status": "healthy" if is_loaded else "model_not_found",
                        "reachable": True,
                        "model": self.model,
                        "hardware": hardware_info,
                        "available_models": model_names
                    }
                return {"status": "unhealthy", "reachable": True, "error": f"Ollama returned {response.status_code}"}
        except Exception as e:
            return {"status": "unreachable", "reachable": False, "error": str(e)}
