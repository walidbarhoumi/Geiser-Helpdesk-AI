from services.ai.ollama_service import OllamaService

class AIClassifier:
    def __init__(self, ollama: OllamaService):
        self.ollama = ollama

    async def classify_intent(self, subject: str, description: str) -> dict:
        """
        Classifies the ticket into categories and determines the intent.
        """
        system_prompt = """
        You are an ITSM Expert. Classify the user request into one of these intents:
        - AUTHENTICATION (Login, password, 2FA)
        - TICKET_MANAGEMENT (Creation, status, assignment issues)
        - INFRASTRUCTURE (Docker, DB, API, PC slow)
        - SECURITY (Phishing, suspicious email)
        - TEAM_MANAGEMENT (Agent/Team creation, workload)
        
        Return JSON: {"intent": "INTENT_NAME", "confidence": 0.0-1.0, "summary": "brief summary"}
        """
        
        prompt = f"Subject: {subject}\nDescription: {description}"
        result = await self.ollama.generate_json(prompt, system_prompt)
        return result if result else {"intent": "GENERAL", "confidence": 0.5, "summary": subject}
