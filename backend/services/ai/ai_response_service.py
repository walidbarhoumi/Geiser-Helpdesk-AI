from motor.motor_asyncio import AsyncIOMotorDatabase
from services.ai.ollama_service import OllamaService
from services.ai.ai_classifier import AIClassifier
from services.ai.suggestion_engine import SuggestionEngine
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class AIResponseService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.ollama = OllamaService()
        self.classifier = AIClassifier(self.ollama)
        self.suggestions = SuggestionEngine(self.ollama)
        self.knowledge_base = db.knowledge_base
        self.history = db.ai_response_history

    async def generate_full_response(self, ticket_id: str, ticket_data: dict) -> dict:
        """
        Orchestrates the full AI response generation:
        1. Classify intent
        2. Lookup Knowledge Base (optional)
        3. Generate professional response via LLM
        4. Generate suggestions
        5. Calculate confidence score
        """
        subject = ticket_data.get("subject", "")
        description = ticket_data.get("description", "")
        
        # 1. Classification
        classification = await self.classifier.classify_intent(subject, description)
        intent = classification.get("intent", "GENERAL")
        summary = classification.get("summary", subject)
        base_confidence = classification.get("confidence", 0.5)

        # 2. Knowledge Base Lookup (Keyword based for now)
        kb_match = await self.knowledge_base.find_one({
            "keywords": {"$in": summary.lower().split()}
        })

        # 3. Generate Response
        if kb_match and base_confidence > kb_match.get("confidence_threshold", 0.7):
            generated_response = kb_match.get("auto_response")
            tech_suggestions = kb_match.get("suggestions", [])
            final_confidence = 0.95 # Higher confidence for KB matches
        else:
            system_prompt = f"""
            You are GEISER AI, a professional ITSM Assistant.
            Generate a polite, helpful, and concise response to the user.
            User Intent: {intent}
            """
            prompt = f"Ticket: {subject}\nDetail: {description}"
            generated_response = await self.ollama.generate_response(prompt, system_prompt)
            tech_suggestions = await self.suggestions.generate_suggestions(intent, summary)
            final_confidence = base_confidence

        # 4. Match Quality
        match_quality = "Weak Match"
        if final_confidence >= 0.9: match_quality = "Excellent Match"
        elif final_confidence >= 0.75: match_quality = "Good Match"

        result = {
            "ticket_id": ticket_id,
            "generated_response": generated_response,
            "suggestions": tech_suggestions,
            "confidence_score": round(final_confidence * 100, 2),
            "match_quality": match_quality,
            "intent": intent,
            "created_at": datetime.utcnow()
        }

        # 5. Save to History
        await self.history.insert_one(result)
        
        # Convert _id for JSON serializability
        if "_id" in result: result["_id"] = str(result["_id"])
        
        return result

    async def save_kb_item(self, item_data: dict):
        item_data["created_at"] = datetime.utcnow()
        await self.knowledge_base.insert_one(item_data)
        return True
