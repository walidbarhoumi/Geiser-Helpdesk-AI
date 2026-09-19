import re
import logging
from typing import Optional, Dict, Any, List
from services.ai.ollama_service import OllamaService
from schemas.schemas import (
    TicketPriority,
    TicketClassificationResponse
)

logger = logging.getLogger(__name__)

# Strict project taxonomy for ITSM Helpdesk GEISER
GEISER_TAXONOMY: Dict[str, List[str]] = {
    "Infrastructure & Réseau": [
        "VPN & Accès Distant",
        "Connexion Wi-Fi / Filaire",
        "Serveurs & Cloud"
    ],
    "Authentification & Accès": [
        "Réinitialisation Mot de passe",
        "Double Facteur (2FA)",
        "Déverrouillage de Compte"
    ],
    "Matériel & Poste de Travail": [
        "PC Portable / Fixe",
        "Imprimante & Scanner",
        "Écran & Périphériques"
    ],
    "Logiciels & Applications": [
        "Suite Office / Messagerie",
        "ERP & Outils Métier",
        "Installation & Mise à jour"
    ],
    "Sécurité IT": [
        "Email Suspect / Phishing",
        "Alerte Antivirus",
        "Incident de Sécurité (ISO 27001)"
    ],
    "Support Général": [
        "Assistance Utilisateur",
        "Autre Demande"
    ]
}


class AIClassifier:
    def __init__(self, ollama: Optional[OllamaService] = None):
        self.ollama = ollama or OllamaService()

    async def classify_intent(self, subject: str, description: str) -> dict:
        """
        Legacy intent classification maintained for backward compatibility with AIResponseService.
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

    async def classify_ticket(self, subject: str, description: str) -> TicketClassificationResponse:
        """
        Real-time AI classification for web ticket creation.
        Uses Ollama LLM if available, with a deterministic heuristic fallback strictly conforming
        to the official GEISER ITSM taxonomy.
        """
        subject_clean = (subject or "").strip()
        desc_clean = (description or "").strip()
        combined = f"{subject_clean}\n{desc_clean}".strip()

        # Attempt LLM Classification
        try:
            llm_result = await self._classify_with_llm(subject_clean, desc_clean)
            if llm_result:
                return llm_result
        except Exception as e:
            logger.warning(f"Ollama LLM classification failed, invoking deterministic heuristic fallback: {e}")

        # Deterministic Heuristic Fallback
        return self._heuristic_classification(subject_clean, desc_clean, combined)

    async def _classify_with_llm(self, subject: str, description: str) -> Optional[TicketClassificationResponse]:
        """Runs LLM prompt with strict taxonomy validation and normalization."""
        system_prompt = f"""Tu es l'analyste ITSM IA de GEISER.
Analyse la demande de support de l'utilisateur (sujet et description) et classe-la STRICTEMENT selon la taxonomie officielle.
Réponds EXCLUSIVEMENT sous forme d'objet JSON valide avec les clés exactes suivantes :

{{
  "category": "Catégorie exacte",
  "subcategory": "Sous-catégorie exacte",
  "priority": "LOW | MEDIUM | HIGH | URGENT",
  "tags": ["tag1", "tag2", "tag3"],
  "confidence": 0.92,
  "reasoning": "Explication courte en français justifiant la catégorie et la priorité retenues."
}}

TAXONOMIE STRICTE AUTORISÉE :
- Infrastructure & Réseau : VPN & Accès Distant, Connexion Wi-Fi / Filaire, Serveurs & Cloud
- Authentification & Accès : Réinitialisation Mot de passe, Double Facteur (2FA), Déverrouillage de Compte
- Matériel & Poste de Travail : PC Portable / Fixe, Imprimante & Scanner, Écran & Périphériques
- Logiciels & Applications : Suite Office / Messagerie, ERP & Outils Métier, Installation & Mise à jour
- Sécurité IT : Email Suspect / Phishing, Alerte Antivirus, Incident de Sécurité (ISO 27001)
- Support Général : Assistance Utilisateur, Autre Demande

RÈGLES DE PRIORITÉ :
- URGENT : Panne bloquante globale, cyberattaque, ransomware, impossibilité totale de travailler.
- HIGH : Incident majeur individuel (VPN bloqué pour télétravail, mot de passe verrouillé sans alternative).
- MEDIUM : Incident fonctionnel avec contournement partiel possible, matériel d'appoint.
- LOW : Demande d'information, question d'usage, requête planifiée sans urgence temporelle.
"""
        prompt = f"Sujet : {subject}\nDescription : {description}"
        raw_data = await self.ollama.generate_json(prompt, system_prompt)

        if not isinstance(raw_data, dict):
            return None

        # 1. Normalize Category
        cat_raw = str(raw_data.get("category", "")).strip()
        category = self._normalize_category(cat_raw)
        if not category:
            return None

        # 2. Normalize Subcategory within validated Category
        subcat_raw = str(raw_data.get("subcategory", "")).strip()
        subcategory = self._normalize_subcategory(category, subcat_raw)

        # 3. Normalize Priority
        prio_raw = str(raw_data.get("priority", "MEDIUM")).upper().strip()
        try:
            priority = TicketPriority(prio_raw)
        except ValueError:
            priority = TicketPriority.MEDIUM

        # 4. Tags
        tags_raw = raw_data.get("tags") or []
        if isinstance(tags_raw, str):
            tags_raw = [t.strip() for t in tags_raw.split(",")]
        tags = [str(t).lower().strip() for t in tags_raw if t]
        if not tags:
            tags = [category.split()[0].lower(), "support"]

        # 5. Internal Confidence
        conf_raw = raw_data.get("confidence")
        try:
            confidence = float(conf_raw) if conf_raw is not None else 0.90
            confidence = max(0.1, min(1.0, round(confidence, 2)))
        except (ValueError, TypeError):
            confidence = 0.88

        # 6. Reasoning
        reasoning = str(raw_data.get("reasoning") or f"Demande classifiée comme incident {category} ({subcategory}) avec priorité {priority.value}.").strip()

        return TicketClassificationResponse(
            category=category,
            subcategory=subcategory,
            priority=priority,
            tags=tags[:6],
            confidence=confidence,
            reasoning=reasoning
        )

    def _normalize_category(self, cat_raw: str) -> Optional[str]:
        """Matches a raw string to the nearest official GEISER category."""
        if cat_raw in GEISER_TAXONOMY:
            return cat_raw

        cat_lower = cat_raw.lower()
        if any(w in cat_lower for w in ["infrastructure", "réseau", "reseau", "network", "vpn", "wifi", "connect"]):
            return "Infrastructure & Réseau"
        if any(w in cat_lower for w in ["auth", "accès", "acces", "mot de passe", "login", "password"]):
            return "Authentification & Accès"
        if any(w in cat_lower for w in ["matériel", "materiel", "hardware", "pc", "ordinateur", "imprimante"]):
            return "Matériel & Poste de Travail"
        if any(w in cat_lower for w in ["logiciel", "software", "application", "office", "outlook", "erp"]):
            return "Logiciels & Applications"
        if any(w in cat_lower for w in ["sécurité", "securite", "security", "phishing", "virus", "antivirus"]):
            return "Sécurité IT"
        if any(w in cat_lower for w in ["support", "général", "general", "autre"]):
            return "Support Général"

        return "Support Général"

    def _normalize_subcategory(self, category: str, subcat_raw: str) -> str:
        """Matches a subcategory to allowed subcategories of the category."""
        allowed = GEISER_TAXONOMY.get(category, ["Assistance Utilisateur", "Autre Demande"])
        for valid in allowed:
            if valid.lower() == subcat_raw.lower():
                return valid

        subcat_lower = subcat_raw.lower()
        for valid in allowed:
            # Substring match
            if valid.lower() in subcat_lower or subcat_lower in valid.lower():
                return valid

        # Fallback to the first standard subcategory of the category
        return allowed[0]

    def _heuristic_classification(self, subject: str, description: str, combined: str) -> TicketClassificationResponse:
        """
        Deterministic, rule-based classification based on the project's tested rules.
        Guarantees 100% adherence to the GEISER taxonomy even if the LLM is offline.
        """
        combined_lower = combined.lower()

        # 1. Determine Priority
        if any(w in combined_lower for w in ["urgent", "bloquant", "critique", "panne totale", "impossible de travailler", "attaque", "piratage", "ransomware"]):
            priority = TicketPriority.URGENT
            prio_reason = "incident bloquant ou critique empêchant le travail"
        elif any(w in combined_lower for w in ["important", "bloqué", "bloque", "erreur", "ne fonctionne pas", "rapide", "échec", "vpn", "accès refusé", "panne"]):
            priority = TicketPriority.HIGH
            prio_reason = "incident à fort impact individuel sur l'activité"
        elif any(w in combined_lower for w in ["information", "question", "comment", "quand", "conseil", "documentation", "renseignement"]):
            priority = TicketPriority.LOW
            prio_reason = "simple demande d'information ou assistance d'usage"
        else:
            priority = TicketPriority.MEDIUM
            prio_reason = "incident opérationnel standard avec prise en charge sous délai habituel"

        # 2. Determine Category, Subcategory & Tags
        if any(w in combined_lower for w in ["vpn", "wifi", "wi-fi", "réseau", "reseau", "connexion", "ip", "dns", "internet", "routeur", "switch", "serveur", "firewall", "cisco", "cloud"]):
            category = "Infrastructure & Réseau"
            if "vpn" in combined_lower or "distant" in combined_lower:
                subcategory = "VPN & Accès Distant"
                tags = ["vpn", "réseau", "connectivité", "télétravail"]
                confidence = 0.94
                tech_reason = "impossibilité d'accès au réseau ou au concentrateur VPN de l'entreprise"
            elif any(w in combined_lower for w in ["serveur", "cloud", "docker", "aws", "vm", "datacenter"]):
                subcategory = "Serveurs & Cloud"
                tags = ["serveur", "cloud", "infrastructure", "hébergement"]
                confidence = 0.91
                tech_reason = "incident lié à l'infrastructure serveur ou aux plateformes cloud"
            else:
                subcategory = "Connexion Wi-Fi / Filaire"
                tags = ["wifi", "réseau", "ethernet", "lan"]
                confidence = 0.90
                tech_reason = "dysfonctionnement de la connexion locale Wi-Fi ou du câblage réseau"

        elif any(w in combined_lower for w in ["mot de passe", "password", "compte", "login", "2fa", "mfa", "authenticator", "accès", "acces", "authentification", "verrouillé", "verrouille", "bloqué"]):
            category = "Authentification & Accès"
            if any(w in combined_lower for w in ["2fa", "mfa", "authenticator", "double facteur"]):
                subcategory = "Double Facteur (2FA)"
                tags = ["2fa", "authenticator", "authentification", "mfa"]
                confidence = 0.95
                tech_reason = "problème de synchronisation ou d'enrôlement du second facteur d'authentification (2FA)"
            elif any(w in combined_lower for w in ["verrouillé", "verrouille", "bloqué", "bloque", "tentatives"]):
                subcategory = "Déverrouillage de Compte"
                tags = ["compte", "active-directory", "verrouillage", "accès"]
                confidence = 0.93
                tech_reason = "compte utilisateur verrouillé suite à de multiples tentatives ou restriction d'accès"
            else:
                subcategory = "Réinitialisation Mot de passe"
                tags = ["mot-de-passe", "password", "compte", "accès"]
                confidence = 0.95
                tech_reason = "demande de réinitialisation sécurisée des identifiants de connexion"

        elif any(w in combined_lower for w in ["phishing", "hameçonnage", "virus", "malware", "suspect", "piratage", "sécurité", "securite", "spam", "alerte", "ransomware"]):
            category = "Sécurité IT"
            if any(w in combined_lower for w in ["antivirus", "malware", "infection", "trojan", "menace"]):
                subcategory = "Alerte Antivirus"
                tags = ["antivirus", "sécurité", "menace", "malware"]
                confidence = 0.94
                tech_reason = "alerte signalant la détection d'un logiciel malveillant ou d'une anomalie par l'antivirus"
            elif any(w in combined_lower for w in ["iso", "27001", "intrusion", "fuite", "compromis", "audit"]):
                subcategory = "Incident de Sécurité (ISO 27001)"
                tags = ["iso-27001", "sécurité", "incident", "conformité"]
                confidence = 0.96
                tech_reason = "incident critique de sécurité de l'information soumis aux règles ISO/IEC 27001"
            else:
                subcategory = "Email Suspect / Phishing"
                tags = ["phishing", "email", "suspect", "sécurité"]
                confidence = 0.95
                tech_reason = "réception d'un courriel suspect présentant des caractéristiques de tentative d'hameçonnage"

        elif any(w in combined_lower for w in ["imprimante", "scanner", "pc", "ordinateur", "écran", "ecran", "souris", "clavier", "matériel", "materiel", "hardware", "disque", "ram"]):
            category = "Matériel & Poste de Travail"
            if any(w in combined_lower for w in ["imprimante", "scanner", "toner", "impression"]):
                subcategory = "Imprimante & Scanner"
                tags = ["imprimante", "matériel", "scanner", "impression"]
                confidence = 0.93
                tech_reason = "panne ou blocage constaté sur le matériel d'impression ou de numérisation"
            elif any(w in combined_lower for w in ["écran", "ecran", "souris", "clavier", "dock", "moniteur", "périphérique"]):
                subcategory = "Écran & Périphériques"
                tags = ["écran", "périphérique", "affichage", "matériel"]
                confidence = 0.91
                tech_reason = "défaut d'affichage ou dysfonctionnement d'un périphérique externe de travail"
            else:
                subcategory = "PC Portable / Fixe"
                tags = ["pc", "poste-de-travail", "matériel", "ordinateur"]
                confidence = 0.90
                tech_reason = "anomalie matérielle constatée sur le poste de travail de l'utilisateur"

        elif any(w in combined_lower for w in ["outlook", "office", "excel", "word", "teams", "logiciel", "application", "erp", "sap", "bug", "installation", "crash"]):
            category = "Logiciels & Applications"
            if any(w in combined_lower for w in ["outlook", "office", "excel", "word", "teams", "messagerie", "mail"]):
                subcategory = "Suite Office / Messagerie"
                tags = ["office", "messagerie", "outlook", "application"]
                confidence = 0.92
                tech_reason = "dysfonctionnement sur les outils de bureautique ou la messagerie d'entreprise"
            elif any(w in combined_lower for w in ["installation", "installer", "mise à jour", "licence", "télécharger"]):
                subcategory = "Installation & Mise à jour"
                tags = ["installation", "mise-à-jour", "logiciel", "licence"]
                confidence = 0.89
                tech_reason = "demande d'installation ou de mise à niveau logicielle pour poste client"
            else:
                subcategory = "ERP & Outils Métier"
                tags = ["erp", "outil-métier", "application", "bug"]
                confidence = 0.88
                tech_reason = "problème d'accès ou d'exécution sur une application métier ou ERP"

        else:
            category = "Support Général"
            subcategory = "Assistance Utilisateur"
            tags = ["support", "assistance", "général"]
            confidence = 0.72
            tech_reason = "demande générale nécessitant un premier niveau de qualification par un agent"

        reasoning = f"Détecté comme {category} > {subcategory} en raison de : {tech_reason}. Priorité {priority.value} assignée ({prio_reason})."

        return TicketClassificationResponse(
            category=category,
            subcategory=subcategory,
            priority=priority,
            tags=tags,
            confidence=confidence,
            reasoning=reasoning
        )
