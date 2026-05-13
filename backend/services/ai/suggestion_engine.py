from typing import List
from services.ai.ollama_service import OllamaService

class SuggestionEngine:
    def __init__(self, ollama: OllamaService):
        self.ollama = ollama

    async def generate_suggestions(self, intent: str, summary: str) -> List[str]:
        """
        Generates 3-5 technical suggestions based on the intent and summary.
        """
        system_prompt = """
        You are a Senior Helpdesk Engineer. 
        Generate 3-5 actionable technical suggestions or resolution steps.
        Format: Return ONLY a JSON list of strings.
        Example: ["Reset password via Forgot Password", "Clear browser cache", "Check LDAP connection"]
        """
        
        prompt = f"Intent: {intent}\nIssue: {summary}"
        result = await self.ollama.generate_json(prompt, system_prompt)
        
        if isinstance(result, list):
            return result
        if isinstance(result, dict) and "suggestions" in result:
            return result["suggestions"]
        return ["Check logs for errors", "Validate user permissions", "Verify network connectivity"]
