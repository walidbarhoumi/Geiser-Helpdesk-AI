from motor.motor_asyncio import AsyncIOMotorDatabase
from datetime import datetime
from typing import List, Dict, Optional
import re
import logging
from bson import ObjectId

from schemas.schemas import (
    ThreadSummaryOut, SuggestedActionItem, InternalDocItem,
    TicketStatus, TicketPriority
)
from services.ai.ollama_service import OllamaService
from models.base import MongoModel

logger = logging.getLogger(__name__)

# Standard GEISER Internal Procedures (SOPs & ISO 27001)
DEFAULT_INTERNAL_SOPS = [
    {
        "title": "SOP-01 : Résolution des Incidents VPN Cisco AnyConnect & Accès Distant",
        "category": "Infrastructure & Réseau",
        "tags": ["vpn", "anyconnect", "réseau", "télétravail", "certificat", "403"],
        "content_snippet": "Procédure standard de réinitialisation du profil AnyConnect, renouvellement des certificats SSL et vidage du cache de routage.",
        "full_content": (
            "PROCÉDURE INTERNE GEISER — SOP-01\n"
            "Objet : Dépannage des accès VPN AnyConnect en télétravail.\n\n"
            "1. Vérification des prérequis :\n"
            "   - S'assurer que le collaborateur dispose d'une connexion internet active (test ping 8.8.8.8).\n"
            "   - Contrôler que le compte Active Directory n'est ni verrouillé ni expiré.\n\n"
            "2. Résolution technique sur le poste client :\n"
            "   a) Fermer Cisco AnyConnect depuis la barre des tâches.\n"
            "   b) Ouvrir PowerShell en Administrateur et exécuter :\n"
            "      ipconfig /flushdns\n"
            "      route -f (nettoyage de la table de routage si conflit d'IP locale)\n"
            "   c) Supprimer les profils corrompus dans : %ProgramData%\\Cisco\\Cisco Secure Client\\VPN\\Profile\\\n"
            "   d) Relancer AnyConnect et saisir la passerelle : vpn.geiser.internal:443\n\n"
            "3. En cas d'erreur 403 (Certificat expiré) :\n"
            "   - Se connecter sur le portail SSO GEISER > Mes Certificats > Renouveler.\n"
            "   - Valider la double authentification (2FA Mobile)."
        ),
        "source_type": "SOP_INTERNE"
    },
    {
        "title": "SOP-02 : Gestion des Mots de Passe & Conformité ISO/IEC 27001",
        "category": "Sécurité & Accès",
        "tags": ["mot de passe", "password", "iso27001", "sécurité", "verrouillage", "ldap", "active directory"],
        "content_snippet": "Exigences ISO 27001 pour la réinitialisation sécurisée des identifiants et le déverrouillage de compte sans divulgation de secret.",
        "full_content": (
            "PROCÉDURE DE SÉCURITÉ GEISER — CONFORME ISO/IEC 27001\n"
            "Objet : Politique d'authentification et assistance réinitialisation mot de passe.\n\n"
            "1. Règle absolue de sécurité ISO 27001 :\n"
            "   - Aucun technicien ne doit jamais demander ou communiquer un mot de passe en clair par email ou chat.\n"
            "   - Toute réinitialisation manuelle requiert la vérification d'identité (Matricule RH + Manager direct).\n\n"
            "2. Déverrouillage d'un compte bloqué (5 tentatives infructueuses) :\n"
            "   - Ouvrir la console Active Directory Users & Computers.\n"
            "   - Rechercher l'utilisateur > Propriétés > Compte > Cocher 'Déverrouiller le compte'.\n\n"
            "3. Génération d'un lien temporaire sécurisé :\n"
            "   - Utiliser le portail self-service : https://idp.geiser.internal/reset\n"
            "   - Le lien à usage unique est expédié sur le canal de secours (téléphone pro / SMS vérifié)."
        ),
        "source_type": "GUIDE_SECURITE_ISO27001"
    },
    {
        "title": "SOP-03 : Diagnostic des Postes de Travail Windows & Lenteurs Système",
        "category": "Matériel & Postes de Travail",
        "tags": ["matériel", "pc lent", "windows", "ram", "cpu", "disque", "écran bleu"],
        "content_snippet": "Guide de dépannage pour postes lents, mémoire saturée, saturation disque et mise à jour de pilotes certifiés GEISER.",
        "full_content": (
            "PROCÉDURE INTERNE GEISER — SOP-03\n"
            "Objet : Optimisation et diagnostic des stations de travail bureautique et CAO.\n\n"
            "1. Diagnostic préliminaire :\n"
            "   - Ouvrir Gestionnaire des Tâches > Performance. Identifier si le goulot est CPU (> 90%), RAM (> 85%) ou Disque.\n"
            "   - Vérifier l'espace disque restant sur C:\\ (un minimum de 15 Go est requis pour les fichiers swap).\n\n"
            "2. Nettoyage standard :\n"
            "   - Exécuter en invite de commande Administrateur :\n"
            "     dism /online /cleanup-image /restorehealth\n"
            "     sfc /scannow\n"
            "   - Vider les fichiers temporaires : %temp% et C:\\Windows\\Temp\n\n"
            "3. En cas de dysfonctionnement matériel avéré :\n"
            "   - Déclencher le remplacement de la barrette RAM ou du SSD via le stock tampon Niveau 2."
        ),
        "source_type": "SOP_INTERNE"
    },
    {
        "title": "SOP-04 : Procédure d'Escalade vers l'Équipe d'Infrastructure & Réseau N2",
        "category": "Infrastructure & Réseau",
        "tags": ["escalade", "n2", "serveur", "switch", "firewall", "coupure", "dns"],
        "content_snippet": "Critères d'escalade d'un incident de Niveau 1 vers les ingénieurs d'infrastructure N2 avec fiche de transmission.",
        "full_content": (
            "PROCÉDURE DE GESTION DES INCIDENTS MAJEURS — SOP-04\n"
            "Objet : Modalités de transmission d'un dossier complexe au pôle N2.\n\n"
            "1. Critères d'escalade :\n"
            "   - L'incident affecte plus de 3 collaborateurs simultanément sur un même site.\n"
            "   - L'incident implique un composant central (serveur de fichiers, pare-feu, DNS d'entreprise, cluster VMware).\n"
            "   - Le délai de résolution N1 dépasse 50% du temps alloué par le SLA sans diagnostic concluant.\n\n"
            "2. Éléments obligatoires dans la fiche d'escalade :\n"
            "   - Description exacte et étapes déjà testées.\n"
            "   - Adresse IP du poste et adresse MAC de la machine.\n"
            "   - Fichiers de logs pertinents joints au ticket.\n"
            "   - Nom de l'ingénieur N2 notifié sur Teams/Slack."
        ),
        "source_type": "SOP_INTERNE"
    },
    {
        "title": "SOP-05 : Gestion de la Messagerie Outlook & Synchronisation Exchange",
        "category": "Logiciels & Applications",
        "tags": ["outlook", "email", "messagerie", "exchange", "boite mail", "calendrier", "ost"],
        "content_snippet": "Résolution des problèmes de synchronisation de boîte aux lettres, profil Outlook corrompu et régénération du fichier .OST.",
        "full_content": (
            "PROCÉDURE INTERNE GEISER — SOP-05\n"
            "Objet : Dépannage messagerie Microsoft 365 / Exchange.\n\n"
            "1. Symptômes courants : Messages bloqués dans la boîte d'envoi, calendrier non synchronisé.\n\n"
            "2. Étapes de résolution :\n"
            "   a) Démarrer Outlook en mode sans échec : outlook.exe /safe\n"
            "   b) Désactiver les compléments tiers suspects (Fichier > Options > Compléments).\n"
            "   c) Reconstruire le fichier de données hors connexion (.ost) :\n"
            "      - Fermer Outlook.\n"
            "      - Aller dans : %localappdata%\\Microsoft\\Outlook\n"
            "      - Renommer le fichier .ost en .ost.old et relancer Outlook pour forcer le téléchargement propre."
        ),
        "source_type": "BASE_CONNAISSANCES"
    }
]


class AgentAssistantService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.tickets = db.tickets
        self.knowledge_base = db.knowledge_base
        self.internal_sops = db.internal_sops
        self.ollama = OllamaService()

    async def ensure_sops_seeded(self):
        """Pre-seed internal SOPs in MongoDB if collection is empty."""
        count = await self.internal_sops.count_documents({})
        if count == 0:
            logger.info("Seeding default GEISER internal SOPs...")
            for sop in DEFAULT_INTERNAL_SOPS:
                sop_doc = dict(sop)
                sop_doc["created_at"] = datetime.utcnow()
                await self.internal_sops.insert_one(sop_doc)

    async def summarize_ticket_thread(self, ticket_id: str) -> ThreadSummaryOut:
        """
        Synthesizes the entire ticket thread (issue, actions taken, blockers, next step).
        """
        oid = MongoModel.to_object_id(ticket_id)
        ticket = await self.tickets.find_one({"_id": oid})
        if not ticket:
            raise ValueError(f"Ticket #{ticket_id} introuvable.")

        subject = ticket.get("subject", "")
        description = ticket.get("description", "")
        category = ticket.get("category", "Général")
        priority = ticket.get("priority", "MEDIUM")
        status = ticket.get("status", "OPEN")
        responses = ticket.get("responses", [])
        resolution_note = ticket.get("resolution_note")

        # Compile thread context
        thread_lines = [f"Demandeur : {description}"]
        for idx, r in enumerate(responses):
            sender = r.get("sender_name") or r.get("role", "Agent")
            content = r.get("content", "")
            thread_lines.append(f"Échange {idx+1} [{sender}] : {content}")

        if resolution_note:
            thread_lines.append(f"Note de résolution enregistrée : {resolution_note}")

        full_thread_text = "\n".join(thread_lines)

        # Call Ollama LLM for executive summary
        system_prompt = """
        Tu es l'assistant IA exécutif des agents support GEISER.
        Analyse la conversation du ticket et produis une synthèse claire, concise et structurée pour l'agent qui reprend le dossier.
        Format de réponse JSON strict :
        {
          "summary": "Résumé en 2 phrases de la situation actuelle...",
          "problem_statement": "Description nette du problème initial rencontré par l'utilisateur",
          "actions_already_taken": ["Action 1 déjà réalisée ou testée", "Action 2..."],
          "current_blocker": "Ce qui bloque actuellement la résolution (ou 'Aucun' si en cours)",
          "suggested_next_step": "La prochaine action concrète recommandée pour l'agent",
          "urgency_evaluation": "Faible / Normale / Élevée / Critique"
        }
        """
        prompt = f"Catégorie : {category} | Priorité : {priority} | Statut : {status}\nSujet : {subject}\n\nFil des échanges :\n{full_thread_text}"

        ai_json = await self.ollama.generate_json(prompt, system_prompt)

        if ai_json and "summary" in ai_json:
            return ThreadSummaryOut(
                ticket_id=ticket_id,
                summary=ai_json.get("summary", ""),
                problem_statement=ai_json.get("problem_statement", subject),
                actions_already_taken=ai_json.get("actions_already_taken", []),
                current_blocker=ai_json.get("current_blocker"),
                suggested_next_step=ai_json.get("suggested_next_step", "Contacter l'utilisateur pour validation"),
                urgency_evaluation=ai_json.get("urgency_evaluation", "Normale")
            )

        # Heuristic fallback if LLM is offline
        actions_done = []
        if responses:
            actions_done.append(f"{len(responses)} réponse(s) d'assistance déjà transmise(s) au demandeur")
        if resolution_note:
            actions_done.append("Une procédure de résolution a été documentée")
        if not actions_done:
            actions_done.append("Ticket nouvellement ouvert — premier contact à établir")

        blocker = "En attente du retour de l'utilisateur" if responses else "Diagnostic technique préliminaire requis"
        next_step = "Appliquer la procédure de résolution standard et demander confirmation du demandeur"

        summary_text = (
            f"L'utilisateur rencontre une anomalie sur « {subject} » ({category}). "
            f"Le dossier est actuellement au statut {status} avec {len(responses)} intervention(s) répertoriée(s)."
        )

        return ThreadSummaryOut(
            ticket_id=ticket_id,
            summary=summary_text,
            problem_statement=f"{subject} — {description[:120]}...",
            actions_already_taken=actions_done,
            current_blocker=blocker,
            suggested_next_step=next_step,
            urgency_evaluation="Élevée" if priority in ["URGENT", "HIGH"] else "Normale"
        )

    async def suggest_smart_actions(self, ticket_id: str) -> List[SuggestedActionItem]:
        """
        Generates 4 to 6 smart recommended next actions for the human agent.
        """
        oid = MongoModel.to_object_id(ticket_id)
        ticket = await self.tickets.find_one({"_id": oid})
        if not ticket:
            raise ValueError(f"Ticket #{ticket_id} introuvable.")

        subject = ticket.get("subject", "").lower()
        desc = ticket.get("description", "").lower()
        category = ticket.get("category", "")
        keywords = [k.lower() for k in (ticket.get("keywords") or [])]
        text_corpus = f"{subject} {desc} {' '.join(keywords)}"

        actions: List[SuggestedActionItem] = []

        # 1. VPN / Network context
        if "vpn" in text_corpus or "réseau" in text_corpus or "connexion" in text_corpus or "infrastructure" in category.lower():
            actions.append(SuggestedActionItem(
                id="act_vpn_cache",
                action_type="DIAGNOSTIC",
                title="Vérifier le cache DNS & l'état RADIUS",
                description="Tester la résolution de nom et la validité du certificat de l'utilisateur sur le serveur d'authentification.",
                snippet_to_insert="Pourriez-vous exécuter la commande 'ipconfig /flushdns' dans une invite de commande et retester la connexion VPN ?",
                impact="HIGH",
                category="Réseau & VPN"
            ))
            actions.append(SuggestedActionItem(
                id="act_remote_support",
                action_type="COMMUNICATION",
                title="Proposer une prise en main à distance",
                description="Planifier une session QuickAssist / TeamViewer pour vérifier le client AnyConnect sur le poste.",
                snippet_to_insert="Si le problème persiste, je vous propose une prise en main à distance rapide de 10 minutes via QuickAssist (Assistance Rapide Windows). Êtes-vous disponible ?",
                impact="MEDIUM",
                category="Assistance Directe"
            ))

        # 2. Authentication / Password context
        elif "mot de passe" in text_corpus or "password" in text_corpus or "compte" in text_corpus or "login" in text_corpus or "sécurité" in category.lower():
            actions.append(SuggestedActionItem(
                id="act_unlock_ad",
                action_type="SYSTEM",
                title="Déverrouiller le compte Active Directory",
                description="Vérifier dans la console LDAP si le compte utilisateur a dépassé le quota des 5 tentatives échouées.",
                snippet_to_insert="Votre compte a été déverrouillé sur notre annuaire d'entreprise. Vous pouvez vous reconnecter avec votre mot de passe habituel.",
                impact="HIGH",
                category="Active Directory"
            ))
            actions.append(SuggestedActionItem(
                id="act_send_reset_link",
                action_type="COMMUNICATION",
                title="Transmettre le portail sécurisé de réinitialisation",
                description="Inviter le collaborateur à choisir un nouveau mot de passe conforme ISO 27001.",
                snippet_to_insert="Veuillez utiliser notre portail sécurisé pour générer votre nouveau mot de passe : https://idp.geiser.internal/reset (minimum 12 caractères, majuscule, chiffre et symbole).",
                impact="MEDIUM",
                category="Sécurité ISO 27001"
            ))

        # 3. Hardware / PC Slow
        elif "pc" in text_corpus or "lent" in text_corpus or "matériel" in text_corpus or "disque" in text_corpus or "écran" in text_corpus:
            actions.append(SuggestedActionItem(
                id="act_sfc_scan",
                action_type="DIAGNOSTIC",
                title="Lancer l'audit de performance & SFC Scan",
                description="Contrôler l'intégrité du système Windows et vérifier l'occupation disque et mémoire.",
                snippet_to_insert="Afin d'optimiser votre poste, pourriez-vous redémarrer complètement la machine (Menu Démarrer > Redémarrer, et non 'Arrêter') afin de purger la mémoire swap ?",
                impact="MEDIUM",
                category="Système Windows"
            ))

        # Generic ITIL standard actions
        actions.append(SuggestedActionItem(
            id="act_request_screenshot",
            action_type="COMMUNICATION",
            title="Demander une capture d'écran de l'erreur",
            description="Demander au demandeur de fournir une capture montrant le code ou message exact d'erreur.",
            snippet_to_insert="Pourriez-vous nous faire parvenir une capture d'écran du message d'erreur complet afin d'affiner notre diagnostic ?",
            impact="LOW",
            category="Information"
        ))

        actions.append(SuggestedActionItem(
            id="act_escalate_n2",
            action_type="ESCALATION",
            title="Escalader vers l'Ingénierie N2 (SOP-04)",
            description="Transférer le ticket à l'équipe spécialisée d'infrastructure si le problème est récurrent ou bloquant.",
            snippet_to_insert="Votre dossier nécessite une intervention approfondie de nos ingénieurs d'infrastructure Niveau 2. Il leur a été transmis en priorité.",
            impact="HIGH",
            category="Escalade"
        ))

        actions.append(SuggestedActionItem(
            id="act_confirm_resolution",
            action_type="SYSTEM",
            title="Clôturer le ticket avec confirmation",
            description="Inviter l'utilisateur à confirmer la bonne marche du service avant clôture définitive.",
            snippet_to_insert="Le service semble être rétabli. Pourriez-vous nous confirmer que tout fonctionne correctement de votre côté afin de clore ce dossier ?",
            impact="MEDIUM",
            category="Clôture"
        ))

        return actions

    async def search_internal_docs(self, query: str, category: Optional[str] = None) -> List[InternalDocItem]:
        """
        Searches GEISER internal SOPs and Knowledge Base articles with relevance scoring.
        """
        await self.ensure_sops_seeded()

        tokens = set(re.findall(r'[a-zA-Z0-9àâäéèêëîïôöùûüç]+', query.lower())) if query else set()

        cursor = self.internal_sops.find()
        sops = await cursor.to_list(100)

        kb_cursor = self.knowledge_base.find()
        kb_articles = await kb_cursor.to_list(100)

        results: List[InternalDocItem] = []

        # Search in SOPs
        for s in sops:
            title = s.get("title", "")
            cat = s.get("category", "")
            tags = [t.lower() for t in s.get("tags", [])]
            content = s.get("full_content", "")
            snippet = s.get("content_snippet", "")

            # If category filter supplied
            if category and category.lower() not in cat.lower():
                continue

            score = 30.0  # base score
            doc_tokens = set(re.findall(r'[a-zA-Z0-9àâäéèêëîïôöùûüç]+', f"{title} {content}".lower())) | set(tags)

            if tokens:
                matched_tokens = tokens.intersection(doc_tokens)
                score += len(matched_tokens) * 15.0

                # Title match bonus
                for tok in tokens:
                    if tok in title.lower():
                        score += 25.0

            score = min(99.0, round(score, 1))

            if not tokens or score >= 40.0:
                results.append(InternalDocItem(
                    id=str(s["_id"]),
                    title=title,
                    category=cat,
                    tags=s.get("tags", []),
                    content_snippet=snippet,
                    full_content=content,
                    relevance_score=score,
                    source_type=s.get("source_type", "SOP_INTERNE")
                ))

        # Search in Knowledge Base
        for kb in kb_articles:
            title = kb.get("title", "Article KB")
            cat = kb.get("category", "Base de connaissances")
            tags = [k.lower() for k in kb.get("keywords", [])]
            auto_resp = kb.get("auto_response", "")

            if category and category.lower() not in cat.lower():
                continue

            score = 30.0
            doc_tokens = set(re.findall(r'[a-zA-Z0-9àâäéèêëîïôöùûüç]+', f"{title} {auto_resp}".lower())) | set(tags)

            if tokens:
                matched_tokens = tokens.intersection(doc_tokens)
                score += len(matched_tokens) * 14.0
                for tok in tokens:
                    if tok in title.lower():
                        score += 20.0

            score = min(98.0, round(score, 1))

            if not tokens or score >= 40.0:
                results.append(InternalDocItem(
                    id=str(kb["_id"]),
                    title=f"KB : {title}",
                    category=cat,
                    tags=kb.get("keywords", []),
                    content_snippet=auto_resp[:180] + "...",
                    full_content=auto_resp,
                    relevance_score=score,
                    source_type="BASE_CONNAISSANCES"
                ))

        # Sort descending by relevance score
        results.sort(key=lambda d: d.relevance_score, reverse=True)
        return results[:8]
