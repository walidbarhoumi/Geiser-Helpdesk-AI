# -*- coding: utf-8 -*-
"""
GEISER Support IA - Enterprise Database Seeder
Populates MongoDB with rich, authentic enterprise data:
- Realistic enterprise users across IT, Finance, HR, R&D, Sales, and Legal
- Organized ITSM support teams with clear specializations
- Dedicated support agents with skills and realistic workloads
- Authentic tickets conforming to the GEISER ITSM taxonomy with detailed descriptions
- Real SLA deadlines, compliance statuses (ON_TRACK, AT_RISK, BREACHED)
- Authentic customer satisfaction (CSAT) ratings and comments
- Real-time notifications and SLA alerts
"""

import asyncio
from datetime import datetime, timedelta
import random
from typing import List, Dict, Any
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient

from core.config import settings
from core.security import get_password_hash
from schemas.schemas import (
    UserRole, TicketPriority, TicketStatus, SLAStatus, TicketChannel,
    ImpactLevel, UrgencyLevel, PrioritySource
)

# Standard dev password hash for "Password123!"
DEV_PASSWORD_HASH = get_password_hash("Password123!")


async def seed_database():
    client = AsyncIOMotorClient(settings.MONGO_URL)
    db = client[settings.DATABASE_NAME]
    print(f"Connecting to database: {settings.DATABASE_NAME}...")

    # ─────────────────────────────────────────────────────────────────────────
    # 1. ENTERPRISE USERS
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- Seeding Users ---")
    
    users_data = [
        # Admin / Superviseur
        {
            "email": "bwalid819@gmail.com",
            "full_name": "Walid Barhoumi",
            "role": UserRole.ADMIN.value,
            "is_active": True,
            "department": "Direction des Systèmes d'Information",
        },
        {
            "email": "claire.dubois@geiser.com",
            "full_name": "Claire Dubois",
            "role": UserRole.SUPERVISOR.value,
            "is_active": True,
            "department": "Support Client & ITSM",
        },

        # Support Agents (N1 / N2 / N3)
        {
            "email": "ahmed.trabelsi@geiser.com",
            "full_name": "Ahmed Trabelsi",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Infrastructure & Réseau",
        },
        {
            "email": "sarah.benali@geiser.com",
            "full_name": "Sarah Benali",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Infrastructure & Réseau",
        },
        {
            "email": "ines.kefi@geiser.com",
            "full_name": "Ines Kefi",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Postes de Travail & Matériel",
        },
        {
            "email": "mohamed.jlassi@geiser.com",
            "full_name": "Mohamed Jlassi",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Postes de Travail & Matériel",
        },
        {
            "email": "amine.garbi@geiser.com",
            "full_name": "Amine Garbi",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Cybersécurité & SOC",
        },
        {
            "email": "mariem.sassi@geiser.com",
            "full_name": "Mariem Sassi",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Cybersécurité & SOC",
        },
        {
            "email": "karim.bouzid@geiser.com",
            "full_name": "Karim Bouzid",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Cloud & DevOps",
        },
        {
            "email": "nour.haddad@geiser.com",
            "full_name": "Nour Haddad",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Cloud & DevOps",
        },
        {
            "email": "youssef.hamdi@geiser.com",
            "full_name": "Youssef Hamdi",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Support Applicatif & ERP",
        },
        {
            "email": "adam9@gmail.com",
            "full_name": "Adam Chemengui",
            "role": UserRole.AGENT.value,
            "is_active": True,
            "department": "Support Applicatif & IA",
        },

        # Enterprise End Users (Collaborateurs métiers)
        {
            "email": "sophie.laurent@geiser.com",
            "full_name": "Sophie Laurent",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Finance & Comptabilité",
        },
        {
            "email": "marc.benamou@geiser.com",
            "full_name": "Marc Benamou",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Contrôle de Gestion",
        },
        {
            "email": "eleonore.dupont@geiser.com",
            "full_name": "Éléonore Dupont",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Ressources Humaines",
        },
        {
            "email": "guillaume.mercier@geiser.com",
            "full_name": "Guillaume Mercier",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Talent Acquisition",
        },
        {
            "email": "camille.roussel@geiser.com",
            "full_name": "Camille Roussel",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "R&D Développements",
        },
        {
            "email": "yassine.mansouri@geiser.com",
            "full_name": "Yassine Mansouri",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Ingénierie & Systèmes",
        },
        {
            "email": "thomas.legrand@geiser.com",
            "full_name": "Thomas Legrand",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Direction Commerciale",
        },
        {
            "email": "amira.khemir@geiser.com",
            "full_name": "Amira Khemir",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Relations Clients Grands Comptes",
        },
        {
            "email": "antoine.lefebvre@geiser.com",
            "full_name": "Antoine Lefebvre",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Direction Juridique & RGPD",
        },
        {
            "email": "julie.fontaine@geiser.com",
            "full_name": "Julie Fontaine",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Logistique & Opérations",
        },
        {
            "email": "user.test@example.com",
            "full_name": "Test User",
            "role": UserRole.USER.value,
            "is_active": True,
            "department": "Qualité & Audit",
        },
    ]

    user_map: Dict[str, ObjectId] = {}
    
    for u in users_data:
        existing = await db.users.find_one({"email": u["email"]})
        if existing:
            user_map[u["email"]] = existing["_id"]
            # update full_name and department if missing
            await db.users.update_one(
                {"_id": existing["_id"]},
                {"$set": {
                    "full_name": u["full_name"],
                    "department": u.get("department", "Général"),
                    "role": u["role"],
                    "is_active": True,
                }}
            )
            print(f"  [Existing] User: {u['full_name']} ({u['email']}) -> {existing['_id']}")
        else:
            doc = {
                "email": u["email"],
                "full_name": u["full_name"],
                "role": u["role"],
                "is_active": u["is_active"],
                "hashed_password": DEV_PASSWORD_HASH,
                "department": u.get("department", "Général"),
                "created_at": datetime.utcnow() - timedelta(days=random.randint(20, 60)),
                "two_factor_enabled": False,
            }
            res = await db.users.insert_one(doc)
            user_map[u["email"]] = res.inserted_id
            print(f"  [Created] User: {u['full_name']} ({u['email']}) -> {res.inserted_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # 2. AGENTS
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- Seeding Agents ---")
    
    agents_spec = [
        {
            "email": "ahmed.trabelsi@geiser.com",
            "username": "ahmed.trabelsi",
            "skills": ["VPN", "Cisco", "Firewall", "Réseau", "Wi-Fi"],
            "is_available": True,
            "workload": 3,
        },
        {
            "email": "sarah.benali@geiser.com",
            "username": "sarah.benali",
            "skills": ["Wi-Fi", "DNS", "Switch", "Cisco", "VLAN", "Réseau"],
            "is_available": True,
            "workload": 2,
        },
        {
            "email": "ines.kefi@geiser.com",
            "username": "ines.kefi",
            "skills": ["PC Hardware", "Windows 11", "Dell", "Matériel", "Écran", "Dock"],
            "is_available": True,
            "workload": 4,
        },
        {
            "email": "mohamed.jlassi@geiser.com",
            "username": "mohamed.jlassi",
            "skills": ["Imprimantes", "HP LaserJet", "Scanner", "Poste de Travail", "Maintenance"],
            "is_available": True,
            "workload": 1,
        },
        {
            "email": "amine.garbi@geiser.com",
            "username": "amine.garbi",
            "skills": ["SOC", "SentinelOne", "Antivirus", "Phishing", "Cybersécurité", "ISO 27001"],
            "is_available": True,
            "workload": 2,
        },
        {
            "email": "mariem.sassi@geiser.com",
            "username": "mariem.sassi",
            "skills": ["SIEM", "Audit Sécurité", "Phishing", "Conformité", "ISO 27001"],
            "is_available": False,
            "workload": 0,
        },
        {
            "email": "karim.bouzid@geiser.com",
            "username": "karim.bouzid",
            "skills": ["Docker", "Kubernetes", "Linux", "Serveurs", "Cloud", "Nginx"],
            "is_available": True,
            "workload": 3,
        },
        {
            "email": "nour.haddad@geiser.com",
            "username": "nour.haddad",
            "skills": ["AWS", "Terraform", "CI/CD", "Docker", "Sauvegardes"],
            "is_available": True,
            "workload": 1,
        },
        {
            "email": "youssef.hamdi@geiser.com",
            "username": "youssef.hamdi",
            "skills": ["SAP Business One", "ERP", "Salesforce", "PostgreSQL", "SQL", "Office 365"],
            "is_available": True,
            "workload": 2,
        },
        {
            "email": "adam9@gmail.com",
            "username": "adam.chemengui",
            "skills": ["Python", "FastAPI", "Suite Office", "Outlook", "Teams", "Power BI"],
            "is_available": True,
            "workload": 2,
        },
    ]

    agent_id_map: Dict[str, ObjectId] = {}

    for ag in agents_spec:
        u_id = user_map.get(ag["email"])
        # Find existing agent by user_id or email
        existing_ag = await db.agents.find_one({"$or": [{"user_id": str(u_id)}, {"user_id": ag["username"]}]})
        if existing_ag:
            agent_id_map[ag["username"]] = existing_ag["_id"]
            await db.agents.update_one(
                {"_id": existing_ag["_id"]},
                {"$set": {
                    "skills": ag["skills"],
                    "is_available": ag["is_available"],
                    "workload": ag["workload"],
                    "user_id": str(u_id) if u_id else ag["username"],
                    "user_email": ag["email"],
                }}
            )
            print(f"  [Updated] Agent: {ag['username']} -> {existing_ag['_id']}")
        else:
            doc = {
                "user_id": str(u_id) if u_id else ag["username"],
                "skills": ag["skills"],
                "is_available": ag["is_available"],
                "workload": ag["workload"],
                "created_at": datetime.utcnow() - timedelta(days=30),
            }
            res = await db.agents.insert_one(doc)
            agent_id_map[ag["username"]] = res.inserted_id
            print(f"  [Created] Agent: {ag['username']} -> {res.inserted_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # 3. TEAMS
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- Seeding Teams ---")

    teams_spec = [
        {
            "name": "Infrastructure Réseau & Télécoms",
            "description": "Administration des équipements réseaux, passerelles VPN d'entreprise, Wi-Fi 6, commutateurs Cisco et liaisons fibres.",
            "competencies": ["Réseau", "VPN", "Cisco", "Firewall", "Wi-Fi", "DNS", "VLAN", "Fibre"],
            "agent_usernames": ["ahmed.trabelsi", "sarah.benali"],
        },
        {
            "name": "Support Matériel & Postes de Travail",
            "description": "Prise en charge des PC portables Dell/Lenovo, stations d'accueil Thunderbolt, moniteurs, imprimantes HP et masterisation Windows 11.",
            "competencies": ["Hardware", "PC Portable", "Dell", "Windows 11", "Imprimante", "macOS", "Périphériques"],
            "agent_usernames": ["ines.kefi", "mohamed.jlassi"],
        },
        {
            "name": "Support Applicatif Métier & ERP",
            "description": "Maintenance et assistance sur les logiciels de gestion, suite Office 365, SAP Business One, Salesforce CRM et outils d'analyse.",
            "competencies": ["SAP", "ERP", "Salesforce", "Office 365", "Outlook", "Excel", "Power BI"],
            "agent_usernames": ["youssef.hamdi", "adam.chemengui"],
        },
        {
            "name": "Cybersécurité & Conformité ISO 27001",
            "description": "Surveillance SOC, analyse des signalements de phishing, alertes EDR SentinelOne et application de la politique ISO 27001.",
            "competencies": ["SOC", "EDR SentinelOne", "Phishing", "SIEM", "ISO 27001", "Audit Sécurité"],
            "agent_usernames": ["amine.garbi", "mariem.sassi"],
        },
        {
            "name": "Infrastructure Cloud & DevOps",
            "description": "Exploitation des serveurs Linux/Windows, clusters Kubernetes, conteneurs Docker, hébergement cloud et stratégies de sauvegarde.",
            "competencies": ["Linux", "Docker", "Kubernetes", "AWS", "Terraform", "Sauvegardes", "Serveurs"],
            "agent_usernames": ["karim.bouzid", "nour.haddad"],
        },
        {
            "name": "Gestion des Identités & Accès (IAM)",
            "description": "Administration Active Directory et Azure AD, réinitialisation de mots de passe, configuration MFA 2FA et clés FIDO2.",
            "competencies": ["Active Directory", "Azure AD", "2FA", "MFA", "FIDO2", "Authentification"],
            "agent_usernames": ["ahmed.trabelsi", "ines.kefi"],
        },
    ]

    team_id_map: Dict[str, ObjectId] = {}

    for t in teams_spec:
        agent_ids = [str(agent_id_map[u]) for u in t["agent_usernames"] if u in agent_id_map]
        existing_t = await db.teams.find_one({"name": t["name"]})
        if existing_t:
            team_id_map[t["name"]] = existing_t["_id"]
            await db.teams.update_one(
                {"_id": existing_t["_id"]},
                {"$set": {
                    "description": t["description"],
                    "competencies": t["competencies"],
                    "agent_ids": agent_ids,
                }}
            )
            print(f"  [Updated] Team: {t['name']} -> {existing_t['_id']}")
        else:
            doc = {
                "name": t["name"],
                "description": t["description"],
                "competencies": t["competencies"],
                "agent_ids": agent_ids,
                "created_at": datetime.utcnow() - timedelta(days=40),
            }
            res = await db.teams.insert_one(doc)
            team_id_map[t["name"]] = res.inserted_id
            print(f"  [Created] Team: {t['name']} -> {res.inserted_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # 4. RICH TICKETS (35 REALISTIC TICKETS)
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- Seeding Authentic Enterprise Tickets ---")

    now = datetime.utcnow()

    tickets_catalog = [
        # --- INFRASTRUCTURE & RÉSEAU ---
        {
            "subject": "Coupure intermittente du VPN FortiClient lors du télétravail",
            "description": "Depuis la mise à jour du client FortiClient 7.2 sur Windows 11, la session VPN se coupe toutes les 25 minutes avec le message d'erreur 'TLS handshake timeout'. Impossible de maintenir une session RDP active vers le serveur comptable.",
            "category": "Infrastructure & Réseau",
            "subcategory": "VPN & Accès Distant",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.IN_PROGRESS.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "sophie.laurent@geiser.com",
            "agent_username": "ahmed.trabelsi",
            "team_name": "Infrastructure Réseau & Télécoms",
            "days_ago": 2,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["vpn", "forticlient", "connexion", "reseau", "teletravail"],
        },
        {
            "subject": "Débit Wi-Fi extrêmement ralenti au 3ème étage aile Sud",
            "description": "Les collaborateurs de l'aile B constatent des temps de réponse anormaux supérieurs à 750ms sur le SSID GEISER-CORP. Les appels visio Teams subissent des gels d'image réguliers.",
            "category": "Infrastructure & Réseau",
            "subcategory": "Connexion Wi-Fi / Filaire",
            "priority": TicketPriority.MEDIUM.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "marc.benamou@geiser.com",
            "agent_username": "sarah.benali",
            "team_name": "Infrastructure Réseau & Télécoms",
            "days_ago": 6,
            "resolution_hours": 3.5,
            "resolution_note": "Borne Cisco Catalyst AP-03 redémarrée et reconfiguration du canal radio 5 GHz pour éliminer les interférences avec le répéteur voisin.",
            "csat_rating": 5,
            "csat_comment": "Intervention rapide et efficace de Sarah. Le Wi-Fi fonctionne à pleine vitesse désormais.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["wifi", "debit", "lenteur", "borne", "cisco"],
        },
        {
            "subject": "Saturation de la bande passante sur la liaison fibre principale",
            "description": "La sonde de monitoring PRTG signale une utilisation constante à 98% du lien fibre 1 Gbps entre 14h et 16h, provoquant des lenteurs sur les services web hébergés.",
            "category": "Infrastructure & Réseau",
            "subcategory": "Serveurs & Cloud",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "yassine.mansouri@geiser.com",
            "agent_username": "ahmed.trabelsi",
            "team_name": "Infrastructure Réseau & Télécoms",
            "days_ago": 12,
            "resolution_hours": 1.5,
            "resolution_note": "Identification d'un job de réplication de base de données non bridé. Mise en place d'une règle QoS et limitation de bande passante à 200 Mbps pendant les heures ouvrées.",
            "csat_rating": 5,
            "csat_comment": "Excellente analyse réseau en temps réel, problème réglé en moins de 2 heures.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["fibre", "bande passante", "saturation", "qos", "monitoring"],
        },
        {
            "subject": "Impossible de joindre le sous-réseau DMZ recette depuis le VPN",
            "description": "La route statique vers 10.150.20.0/24 semble absente de la table de routage attribuée par la passerelle VPN. Blocage complet pour la validation de la release v2.4.",
            "category": "Infrastructure & Réseau",
            "subcategory": "VPN & Accès Distant",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.OPEN.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "camille.roussel@geiser.com",
            "days_ago": 0.5,
            "sla_status": SLAStatus.AT_RISK.value,
            "keywords": ["vpn", "dmz", "routage", "recette", "ip"],
        },
        {
            "subject": "Prise réseau RJ45 murale inactive dans la salle de réunion Kilimandjaro",
            "description": "Le port mural RJ45 n°K-04 ne délivre aucune liaison Ethernet (LED link éteinte). Les réunions avec le board nécessitent une connexion filaire stable.",
            "category": "Infrastructure & Réseau",
            "subcategory": "Connexion Wi-Fi / Filaire",
            "priority": TicketPriority.LOW.value,
            "status": TicketStatus.CLOSED.value,
            "channel": TicketChannel.CHAT.value,
            "user_email": "thomas.legrand@geiser.com",
            "agent_username": "sarah.benali",
            "team_name": "Infrastructure Réseau & Télécoms",
            "days_ago": 18,
            "resolution_hours": 12.0,
            "resolution_note": "Rebrassage du port sur le commutateur de baie Bâtiment A, port switch 24 réactivé en VLAN 10.",
            "csat_rating": 4,
            "csat_comment": "Prise réparée avant la réunion commerciale, parfait.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["rj45", "ethernet", "prise", "reunion", "cable"],
        },

        # --- AUTHENTIFICATION & ACCÈS ---
        {
            "subject": "Compte Active Directory verrouillé après retour de congés",
            "description": "Suite à la saisie répétée d'un ancien mot de passe après deux semaines de congés, mon compte 'eleonore.dupont' a été verrouillé. Je ne peux plus ouvrir ma session Windows ni accéder aux dossiers du personnel.",
            "category": "Authentification & Accès",
            "subcategory": "Déverrouillage de Compte",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "eleonore.dupont@geiser.com",
            "agent_username": "ahmed.trabelsi",
            "team_name": "Gestion des Identités & Accès (IAM)",
            "days_ago": 4,
            "resolution_hours": 0.3,
            "resolution_note": "Compte AD déverrouillé dans Active Directory Users & Computers. Mot de passe temporaire transmis de manière sécurisée par SMS.",
            "csat_rating": 5,
            "csat_comment": "Débloqué en 10 minutes chrono, merci infiniment !",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["active directory", "verrouille", "mot de passe", "session", "ad"],
        },
        {
            "subject": "Changement de smartphone : réinitialisation de l'application 2FA",
            "description": "J'ai renouvelé mon smartphone professionnel. L'application Microsoft Authenticator est vide et je ne reçois plus les codes de validation à double facteur pour le portail ERP.",
            "category": "Authentification & Accès",
            "subcategory": "Double Facteur (2FA)",
            "priority": TicketPriority.MEDIUM.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.CHAT.value,
            "user_email": "guillaume.mercier@geiser.com",
            "agent_username": "ines.kefi",
            "team_name": "Gestion des Identités & Accès (IAM)",
            "days_ago": 7,
            "resolution_hours": 1.2,
            "resolution_note": "Régénération du code QR d'enrôlement MFA Azure AD après vérification de l'identité par appel managérial.",
            "csat_rating": 5,
            "csat_comment": "Super prise en charge, configuration du nouveau téléphone très simple.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["2fa", "mfa", "authenticator", "double facteur", "smartphone"],
        },
        {
            "subject": "Expiration du mot de passe Office 365 et blocage de la messagerie mobile",
            "description": "Mon mot de passe Office 365 a expiré ce week-end. Depuis ce matin, l'application Outlook sur mon iPhone me demande un mot de passe en boucle et rejette la nouvelle saisie.",
            "category": "Authentification & Accès",
            "subcategory": "Réinitialisation Mot de passe",
            "priority": TicketPriority.MEDIUM.value,
            "status": TicketStatus.IN_PROGRESS.value,
            "channel": TicketChannel.EMAIL.value,
            "user_email": "amira.khemir@geiser.com",
            "agent_username": "ines.kefi",
            "team_name": "Gestion des Identités & Accès (IAM)",
            "days_ago": 1,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["mot de passe", "office 365", "outlook", "expiration", "mobile"],
        },
        {
            "subject": "Clé de sécurité FIDO2 USB non détectée sur le portail Webmail",
            "description": "Lors de la tentative d'authentification sur le portail sécurisé, la clé YubiKey FIDO2 clignote mais le navigateur affiche l'erreur 'Dispositif de sécurité non reconnu ou non autorisé'.",
            "category": "Authentification & Accès",
            "subcategory": "Double Facteur (2FA)",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.OPEN.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "antoine.lefebvre@geiser.com",
            "days_ago": 0.8,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["fido2", "yubikey", "2fa", "cle usb", "securite"],
        },
        {
            "subject": "Accès refusé au portail RH interne - erreur de droits Kerberos",
            "description": "Message d'erreur HTTP 403 Forbidden et ticket Kerberos non renouvelé lors de la consultation des dossiers de formation sur le serveur intranet.",
            "category": "Authentification & Accès",
            "subcategory": "Déverrouillage de Compte",
            "priority": TicketPriority.LOW.value,
            "status": TicketStatus.CLOSED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "julie.fontaine@geiser.com",
            "agent_username": "ahmed.trabelsi",
            "team_name": "Gestion des Identités & Accès (IAM)",
            "days_ago": 22,
            "resolution_hours": 5.0,
            "resolution_note": "Ajout du compte utilisateur dans le groupe Active Directory 'GG_PORTAIL_RH_LECTURE' et purge du ticket Kerberos via klist purge.",
            "csat_rating": 4,
            "csat_comment": "Accès rétabli dans la journée.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["kerberos", "droits", "portail rh", "acces refuse", "active directory"],
        },

        # --- MATÉRIEL & POSTE DE TRAVAIL ---
        {
            "subject": "Batterie déformée et surchauffe anormale sur Dell Latitude 5530",
            "description": "Le châssis inférieur de mon ordinateur portable s'est ouvert sur le côté et le trackpad clique très difficilement. La batterie semble avoir gonflé. PC éteint par précaution dans l'attente d'un remplacement.",
            "category": "Matériel & Poste de Travail",
            "subcategory": "PC Portable / Fixe",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "sophie.laurent@geiser.com",
            "agent_username": "ines.kefi",
            "team_name": "Support Matériel & Postes de Travail",
            "days_ago": 8,
            "resolution_hours": 4.0,
            "resolution_note": "Mise à disposition immédiate d'un PC portable de prêt Dell Latitude 5540 avec clonage du profil et commande d'une batterie d'origine Dell sous garantie.",
            "csat_rating": 5,
            "csat_comment": "Prise en charge exemplaire pour un problème de sécurité matérielle. Merci Ines !",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["batterie", "dell", "surchauffe", "materiel", "chassis"],
        },
        {
            "subject": "Code erreur 13.02 et bourrage papier persistant sur l'imprimante HP LaserJet RH",
            "description": "Le bac 2 de l'imprimante multifonction du service RH n'entraîne plus le papier et affiche le code '13.02.00 Papier coincé'. Les contrats de travail ne peuvent plus être édités.",
            "category": "Matériel & Poste de Travail",
            "subcategory": "Imprimante & Scanner",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.IN_PROGRESS.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "eleonore.dupont@geiser.com",
            "agent_username": "mohamed.jlassi",
            "team_name": "Support Matériel & Postes de Travail",
            "days_ago": 1.2,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["imprimante", "bourrage", "hp laserjet", "papier", "erreur 13.02"],
        },
        {
            "subject": "Station d'accueil Thunderbolt Dell WD19S ne transmet plus l'affichage vidéo",
            "description": "Depuis ce matin, les deux moniteurs externes restent noirs lorsque le PC est branché sur le dock USB-C Thunderbolt. Clavier et souris USB fonctionnent mais pas les sorties DisplayPort.",
            "category": "Matériel & Poste de Travail",
            "subcategory": "Écran & Périphériques",
            "priority": TicketPriority.MEDIUM.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "marc.benamou@geiser.com",
            "agent_username": "ines.kefi",
            "team_name": "Support Matériel & Postes de Travail",
            "days_ago": 14,
            "resolution_hours": 2.0,
            "resolution_note": "Mise à jour du firmware du dock Dell WD19S vers la version 01.00.25 et réinstallation des pilotes graphiques Intel Iris Xe.",
            "csat_rating": 5,
            "csat_comment": "Le double écran refonctionne à merveille.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["dock", "thunderbolt", "ecran", "displayport", "dell"],
        },
        {
            "subject": "Écran bleu BSOD systématique (CRITICAL_PROCESS_DIED) au démarrage",
            "description": "L'ordinateur portable du chef de projet R&D crashe au bout de 2 minutes sur l'écran bleu Windows avec le code CRITICAL_PROCESS_DIED. Impossible de travailler en l'état.",
            "category": "Matériel & Poste de Travail",
            "subcategory": "PC Portable / Fixe",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.IN_PROGRESS.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "yassine.mansouri@geiser.com",
            "agent_username": "ines.kefi",
            "team_name": "Support Matériel & Postes de Travail",
            "days_ago": 0.4,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["bsod", "ecran bleu", "crash", "windows 11", "demarrage"],
        },
        {
            "subject": "Casque Jabra sans fil grésille et coupe la voix sur Teams",
            "description": "Le micro du micro-casque Jabra Evolve2 65 se désactive brutalement en pleine conversation avec des prospects. Le dongle USB Jabra Link 380 clignote en rouge.",
            "category": "Matériel & Poste de Travail",
            "subcategory": "Écran & Périphériques",
            "priority": TicketPriority.LOW.value,
            "status": TicketStatus.CLOSED.value,
            "channel": TicketChannel.CHAT.value,
            "user_email": "thomas.legrand@geiser.com",
            "agent_username": "mohamed.jlassi",
            "team_name": "Support Matériel & Postes de Travail",
            "days_ago": 25,
            "resolution_hours": 24.0,
            "resolution_note": "Mise à jour du firmware Jabra Direct et appairage neuf sur un port USB-A natif sans hub.",
            "csat_rating": 4,
            "csat_comment": "Plus aucun grésillement en rendez-vous client.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["casque", "jabra", "teams", "micro", "peripherique"],
        },

        # --- LOGICIELS & APPLICATIONS ---
        {
            "subject": "Outlook 365 se fige au démarrage sur 'Chargement du profil'",
            "description": "Au lancement d'Outlook, la fenêtre reste bloquée indéfiniment sur 'Chargement du profil'. La désactivation du mode sans échec ne change rien. Plusieurs gigaoctets de mails non synchronisés.",
            "category": "Logiciels & Applications",
            "subcategory": "Suite Office / Messagerie",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "antoine.lefebvre@geiser.com",
            "agent_username": "adam.chemengui",
            "team_name": "Support Applicatif Métier & ERP",
            "days_ago": 5,
            "resolution_hours": 1.5,
            "resolution_note": "Fichier de cache local OST corrompu. Recréation d'un profil de messagerie neuf et resynchronisation complète de la boîte Exchange.",
            "csat_rating": 5,
            "csat_comment": "Super réactivité, tous mes mails et dossiers sont réapparus sans perte.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["outlook", "chargement", "profil", "office 365", "ost"],
        },
        {
            "subject": "Erreur d'exportation comptable SQL-304 sous SAP Business One",
            "description": "La tentative d'exportation du journal des ventes vers le logiciel de révision fiscale échoue avec l'erreur 'Exception SQL-304: Deadlock encountered on table OINV'. Clôture mensuelle bloquée.",
            "category": "Logiciels & Applications",
            "subcategory": "ERP & Outils Métier",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "sophie.laurent@geiser.com",
            "agent_username": "youssef.hamdi",
            "team_name": "Support Applicatif Métier & ERP",
            "days_ago": 15,
            "resolution_hours": 2.5,
            "resolution_note": "Kill de la transaction fantôme sur le serveur SQL PostgreSQL/SAP et optimisation de l'index sur la table OINV. Export relancé avec succès.",
            "csat_rating": 5,
            "csat_comment": "Merci Youssef, clôture comptable sauvée in extremis !",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["sap", "erp", "sql", "exportation", "comptabilite"],
        },
        {
            "subject": "Demande de licence Power BI Pro pour l'équipe Contrôle de Gestion",
            "description": "Besoin de publier et partager les dashboards budgétaires Q4 sur l'espace de travail sécurisé Power BI Service. Accord budgétaire du DAF en pièce jointe.",
            "category": "Logiciels & Applications",
            "subcategory": "Installation & Mise à jour",
            "priority": TicketPriority.LOW.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "marc.benamou@geiser.com",
            "agent_username": "adam.chemengui",
            "team_name": "Support Applicatif Métier & ERP",
            "days_ago": 9,
            "resolution_hours": 8.0,
            "resolution_note": "Attribution de la licence Power BI Pro depuis le centre d'administration Microsoft 365 et attribution des droits sur le workspace 'CDG-Q4'.",
            "csat_rating": 5,
            "csat_comment": "Licence activée rapidement, dashboards en ligne.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["power bi", "licence", "installation", "rapport", "dashboard"],
        },
        {
            "subject": "Échec de synchronisation des leads et devis dans Salesforce CRM",
            "description": "Le connecteur entre la boutique en ligne et Salesforce ne remonte plus les nouveaux devis depuis hier soir. Code d'erreur API 'INVALID_SESSION_ID'.",
            "category": "Logiciels & Applications",
            "subcategory": "ERP & Outils Métier",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.IN_PROGRESS.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "amira.khemir@geiser.com",
            "agent_username": "youssef.hamdi",
            "team_name": "Support Applicatif Métier & ERP",
            "days_ago": 1.8,
            "sla_status": SLAStatus.AT_RISK.value,
            "keywords": ["salesforce", "crm", "synchronisation", "api", "devis"],
        },
        {
            "subject": "Crash de Microsoft Teams au lancement avec code d'erreur CAA2000B",
            "description": "L'application Teams sur poste de travail crashe immédiatement après ouverture avec l'erreur 'CAA2000B - Échec de validation du token de session'.",
            "category": "Logiciels & Applications",
            "subcategory": "Suite Office / Messagerie",
            "priority": TicketPriority.MEDIUM.value,
            "status": TicketStatus.OPEN.value,
            "channel": TicketChannel.CHAT.value,
            "user_email": "guillaume.mercier@geiser.com",
            "days_ago": 0.3,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["teams", "crash", "office", "erreur caa2000b", "connexion"],
        },

        # --- SÉCURITÉ IT (ISO 27001) ---
        {
            "subject": "Signalement d'un email de phishing ciblé usurpant la Direction Financière",
            "description": "Plusieurs comptables ont reçu un email avec pour objet 'URGENT : Demande d'actualisation de coordonnées bancaires' provenant de l'adresse spoofée 'direction@geiser-financial-group.com'. Aucune pièce jointe ouverte.",
            "category": "Sécurité IT",
            "subcategory": "Email Suspect / Phishing",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.EMAIL.value,
            "user_email": "sophie.laurent@geiser.com",
            "agent_username": "amine.garbi",
            "team_name": "Cybersécurité & Conformité ISO 27001",
            "days_ago": 3,
            "resolution_hours": 0.8,
            "resolution_note": "Domaine émetteur bloqué sur la passerelle de messagerie Proofpoint. Règle de suppression automatique appliquée sur l'ensemble des boîtes de l'entreprise. Signalement classé incident mineur ISO 27001 sans fuite de données.",
            "csat_rating": 5,
            "csat_comment": "Réactivité impressionnante de la sécurité, merci pour la protection de l'équipe.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["phishing", "email suspect", "securite", "usurpation", "soc"],
        },
        {
            "subject": "Alerte SentinelOne : Détection d'un script PowerShell suspect dans AppData",
            "description": "La console EDR a levé une alerte de sévérité élevée sur le poste de l'utilisateur 'guillaume.mercier'. Processus powershell.exe tentant une connexion sortante vers une adresse IP inconnue.",
            "category": "Sécurité IT",
            "subcategory": "Alerte Antivirus",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "guillaume.mercier@geiser.com",
            "agent_username": "amine.garbi",
            "team_name": "Cybersécurité & Conformité ISO 27001",
            "days_ago": 11,
            "resolution_hours": 1.1,
            "resolution_note": "Poste isolé du réseau via l'agent SentinelOne. Analyse mémoire effectuée : faux positif causé par un script d'inventaire RH légitime d'une solution SaaS de paie. Règle d'exclusion créée.",
            "csat_rating": 5,
            "csat_comment": "Procédure d'isolement rassurante et explication limpide du technicien sécurité.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["antivirus", "sentinelone", "powershell", "edr", "securite"],
        },
        {
            "subject": "Déclaration de perte de badge physique d'accès aux locaux (ISO 27001)",
            "description": "Perte de mon badge nominatif d'accès au siège social n°88419 ce matin dans les transports en commun. Demande de révocation immédiate du badge dans le système de contrôle d'accès.",
            "category": "Sécurité IT",
            "subcategory": "Incident de Sécurité (ISO 27001)",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "camille.roussel@geiser.com",
            "agent_username": "mariem.sassi",
            "team_name": "Cybersécurité & Conformité ISO 27001",
            "days_ago": 16,
            "resolution_hours": 0.5,
            "resolution_note": "Badge désactivé immédiatement dans la base Nedap. Émission d'un badge temporaire et enregistrement au registre des incidents physiques ISO 27001.",
            "csat_rating": 5,
            "csat_comment": "Badge coupé en 5 minutes, sécurité assurée.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["badge", "perte", "iso 27001", "acces physique", "securite"],
        },
        {
            "subject": "Révocation urgente de tous les accès pour départ de collaborateur",
            "description": "Départ avec effet immédiat d'un collaborateur commercial. Procédure ISO 27001 : désactiver immédiatement le compte Active Directory, révoquer les sessions Office 365, Salesforce et VPN.",
            "category": "Sécurité IT",
            "subcategory": "Incident de Sécurité (ISO 27001)",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.CLOSED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "eleonore.dupont@geiser.com",
            "agent_username": "amine.garbi",
            "team_name": "Cybersécurité & Conformité ISO 27001",
            "days_ago": 20,
            "resolution_hours": 0.4,
            "resolution_note": "Comptes bloqués, jetons JWT révoqués, boîte mail convertie en boîte partagée sous contrôle de la direction commerciale.",
            "csat_rating": 5,
            "csat_comment": "Procédure parfaitement respectée.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["revocation", "depart", "iso 27001", "active directory", "securite"],
        },
        {
            "subject": "Email suspect contenant une archive ZIP protégée par mot de passe",
            "description": "Courriel externe prétendant contenir une facture impayée dans un fichier ZIP verrouillé avec mot de passe dans le corps du texte. Comportement suspect.",
            "category": "Sécurité IT",
            "subcategory": "Email Suspect / Phishing",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.OPEN.value,
            "channel": TicketChannel.EMAIL.value,
            "user_email": "julie.fontaine@geiser.com",
            "days_ago": 0.2,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["phishing", "zip", "malware", "email suspect", "antivirus"],
        },

        # --- CLOUD & DEVOPS ---
        {
            "subject": "Dégradation des performances sur le cluster Kubernetes de production",
            "description": "Le nœud 'k8s-worker-04' est passé en état NotReady suite à une saturation mémoire (OOMKilled) sur les pods d'indexation vectorielle. Basculement partiel du trafic.",
            "category": "Infrastructure & Réseau",
            "subcategory": "Serveurs & Cloud",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.IN_PROGRESS.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "camille.roussel@geiser.com",
            "agent_username": "karim.bouzid",
            "team_name": "Infrastructure Cloud & DevOps",
            "days_ago": 0.6,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["kubernetes", "cluster", "oomkilled", "docker", "cloud"],
        },
        {
            "subject": "Échec du pipeline CI/CD GitLab lors du déploiement en préproduction",
            "description": "Le job 'deploy_staging' renvoie l'erreur 'ImagePullBackOff - authenticating to AWS ECR failed'. Le token de registre AWS a expiré.",
            "category": "Infrastructure & Réseau",
            "subcategory": "Serveurs & Cloud",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "yassine.mansouri@geiser.com",
            "agent_username": "nour.haddad",
            "team_name": "Infrastructure Cloud & DevOps",
            "days_ago": 10,
            "resolution_hours": 1.2,
            "resolution_note": "Rotation des clés IAM AWS et mise à jour des variables de CI/CD GitLab protégées. Pipeline relancé avec succès.",
            "csat_rating": 5,
            "csat_comment": "Pipeline réparé très vite par Nour, livraisons débloquées.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["gitlab", "ci/cd", "aws", "docker", "pipeline"],
        },
        {
            "subject": "Certificat SSL Let's Encrypt expiré sur le sous-domaine doc.geiser.internal",
            "description": "Les navigateurs affichent un avertissement de sécurité 'Votre connexion n'est pas privée (ERR_CERT_DATE_INVALID)' lors de l'accès à la documentation interne.",
            "category": "Infrastructure & Réseau",
            "subcategory": "Serveurs & Cloud",
            "priority": TicketPriority.MEDIUM.value,
            "status": TicketStatus.CLOSED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "camille.roussel@geiser.com",
            "agent_username": "karim.bouzid",
            "team_name": "Infrastructure Cloud & DevOps",
            "days_ago": 28,
            "resolution_hours": 2.0,
            "resolution_note": "Renouvellement via certbot et correction de la tâche cron de renouvellement automatique sur le reverse-proxy Nginx.",
            "csat_rating": 4,
            "csat_comment": "Certificat renouvelé, documentation accessible.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["ssl", "certificat", "nginx", "https", "securite"],
        },

        # --- SUPPORT GÉNÉRAL ---
        {
            "subject": "Configuration de la signature électronique qualifiée sur Adobe Acrobat",
            "description": "Besoin d'aide pour importer et certifier le certificat d'entreprise RGS** afin de signer électroniquement des contrats d'achat engageant la société.",
            "category": "Support Général",
            "subcategory": "Assistance Utilisateur",
            "priority": TicketPriority.LOW.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "antoine.lefebvre@geiser.com",
            "agent_username": "ines.kefi",
            "team_name": "Support Matériel & Postes de Travail",
            "days_ago": 13,
            "resolution_hours": 3.0,
            "resolution_note": "Session d'assistance à distance Teams : installation du module de signature et test validé avec succès sur un document modèle.",
            "csat_rating": 5,
            "csat_comment": "Excellente assistance pédagogique d'Ines. Signature opérationnelle.",
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["adobe", "signature electronique", "acrobat", "certificat", "contrat"],
        },
        {
            "subject": "Demande de kit de télétravail : souris ergonomique et double écran",
            "description": "Conformément à la convention de télétravail validée par la médecine du travail et les RH, demande d'un moniteur 24 pouces et d'une souris verticale Logitech MX Master.",
            "category": "Support Général",
            "subcategory": "Autre Demande",
            "priority": TicketPriority.LOW.value,
            "status": TicketStatus.IN_PROGRESS.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "julie.fontaine@geiser.com",
            "agent_username": "ines.kefi",
            "team_name": "Support Matériel & Postes de Travail",
            "days_ago": 3.5,
            "sla_status": SLAStatus.ON_TRACK.value,
            "keywords": ["teletravail", "materiel", "ecran", "souris", "ergonomie"],
        },

        # --- TICKETS AVEC CAS PARTICULIERS SLA (BREACHED & AT_RISK POUR STATS AUTHENTIQUES) ---
        {
            "subject": "Panne persistante du scanner réseau Bâtiment C",
            "description": "Le scanner réseau refuse les envois vers les dossiers partagés avec code erreur SMB-004. Ticket resté en attente de pièces détachées.",
            "category": "Matériel & Poste de Travail",
            "subcategory": "Imprimante & Scanner",
            "priority": TicketPriority.MEDIUM.value,
            "status": TicketStatus.IN_PROGRESS.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "julie.fontaine@geiser.com",
            "agent_username": "mohamed.jlassi",
            "team_name": "Support Matériel & Postes de Travail",
            "days_ago": 5,
            "sla_status": SLAStatus.BREACHED.value,
            "sla_breached_at": now - timedelta(days=2),
            "keywords": ["scanner", "smb", "imprimante", "panne", "reseau"],
        },
        {
            "subject": "Lenteur extrême d'accès aux disques réseau depuis le site distant de Lyon",
            "description": "Le VPN inter-sites entre Paris et Lyon subit un taux de perte de paquets de 15%. Les ouvertures de fichiers Excel prennent plus de 4 minutes.",
            "category": "Infrastructure & Réseau",
            "subcategory": "VPN & Accès Distant",
            "priority": TicketPriority.HIGH.value,
            "status": TicketStatus.OPEN.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "thomas.legrand@geiser.com",
            "days_ago": 1.5,
            "sla_status": SLAStatus.BREACHED.value,
            "sla_breached_at": now - timedelta(hours=6),
            "keywords": ["vpn", "lenteur", "site distant", "lyon", "reseau"],
        },
        {
            "subject": "Blocage de l'accès comptable aux états de paye du mois",
            "description": "Droits manquants sur le répertoire \\SRV-RH\\Paies_2026. Clôture des fiches de paye en attente urgente.",
            "category": "Authentification & Accès",
            "subcategory": "Déverrouillage de Compte",
            "priority": TicketPriority.URGENT.value,
            "status": TicketStatus.RESOLVED.value,
            "channel": TicketChannel.WEB.value,
            "user_email": "sophie.laurent@geiser.com",
            "agent_username": "ahmed.trabelsi",
            "team_name": "Gestion des Identités & Accès (IAM)",
            "days_ago": 7,
            "resolution_hours": 6.0,  # Breached SLA for urgent (allowed 4.0h)
            "resolution_note": "Permissions NTFS réaccordées après validation de la DRH. Résolution avec dépassement du délai de prise en charge initial.",
            "csat_rating": 3,
            "csat_comment": "Problème réglé, mais délai un peu long pour une clôture de paye urgente.",
            "sla_status": SLAStatus.BREACHED.value,
            "sla_breached_at": now - timedelta(days=6, hours=18),
            "keywords": ["paye", "droits", "repertoire", "comptabilite", "urgent"],
        },
    ]

    inserted_ticket_ids: List[ObjectId] = []
    created_tickets_docs: List[Dict[str, Any]] = []

    for t in tickets_catalog:
        u_id = user_map.get(t["user_email"])
        if not u_id:
            u_id = user_map.get("bwalid819@gmail.com")

        created_at = now - timedelta(days=t["days_ago"])
        updated_at = created_at + timedelta(hours=t.get("resolution_hours", random.uniform(0.5, 4.0)))

        agent_id = None
        if t.get("agent_username") and t["agent_username"] in agent_id_map:
            agent_id = str(agent_id_map[t["agent_username"]])

        team_id = None
        if t.get("team_name") and t["team_name"] in team_id_map:
            team_id = str(team_id_map[t["team_name"]])

        # ITIL impact & urgency
        prio = TicketPriority(t["priority"])
        if prio == TicketPriority.URGENT:
            impact, urgency = ImpactLevel.HIGH, UrgencyLevel.HIGH
            sla_hours = 4.0
        elif prio == TicketPriority.HIGH:
            impact, urgency = ImpactLevel.HIGH, UrgencyLevel.MEDIUM
            sla_hours = 8.0
        elif prio == TicketPriority.MEDIUM:
            impact, urgency = ImpactLevel.MEDIUM, UrgencyLevel.MEDIUM
            sla_hours = 24.0
        else:
            impact, urgency = ImpactLevel.LOW, UrgencyLevel.LOW
            sla_hours = 72.0

        sla_deadline = created_at + timedelta(hours=sla_hours)

        ticket_doc = {
            "subject": t["subject"],
            "description": t["description"],
            "category": t["category"],
            "subcategory": t["subcategory"],
            "priority": t["priority"],
            "impact": impact.value,
            "urgency": urgency.value,
            "priority_source": PrioritySource.ITIL_MATRIX.value,
            "channel": t["channel"],
            "status": t["status"],
            "user_id": str(u_id),
            "assigned_agent_id": agent_id,
            "assigned_team_id": team_id,
            "routing_reason": f"Routage automatique vers {t.get('team_name', 'Équipe')} sur la base des compétences ({', '.join(t.get('keywords', []))}).",
            "attachments": [],
            "keywords": t.get("keywords", []),
            "resolution_note": t.get("resolution_note"),
            "responses": [],
            "satisfaction_rating": t.get("csat_rating"),
            "satisfaction_comment": t.get("csat_comment"),
            "satisfaction_submitted_at": updated_at if t.get("csat_rating") else None,
            "sla_deadline": sla_deadline,
            "sla_status": t.get("sla_status", SLAStatus.ON_TRACK.value),
            "sla_breached_at": t.get("sla_breached_at"),
            "created_at": created_at,
            "updated_at": updated_at,
        }

        # Check if already inserted by subject
        existing = await db.tickets.find_one({"subject": t["subject"]})
        if existing:
            await db.tickets.update_one({"_id": existing["_id"]}, {"$set": ticket_doc})
            inserted_ticket_ids.append(existing["_id"])
            created_tickets_docs.append({**ticket_doc, "_id": existing["_id"]})
            print(f"  [Updated Ticket] {t['subject'][:50]}... -> {existing['_id']}")
        else:
            res = await db.tickets.insert_one(ticket_doc)
            inserted_ticket_ids.append(res.inserted_id)
            created_tickets_docs.append({**ticket_doc, "_id": res.inserted_id})
            print(f"  [Created Ticket] {t['subject'][:50]}... -> {res.inserted_id}")

    # ─────────────────────────────────────────────────────────────────────────
    # 5. REALISTIC NOTIFICATIONS
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- Seeding Notifications ---")

    admin_user_id = str(user_map["bwalid819@gmail.com"])

    notifications_data = [
        {
            "user_id": admin_user_id,
            "channel": "EMAIL",
            "title": "Alerte Sécurité ISO 27001",
            "message": "Incident de phishing ciblé détecté et bloqué sur la passerelle Proofpoint.",
            "status": "SENT",
            "days_ago": 3,
        },
        {
            "user_id": admin_user_id,
            "channel": "IN_APP",
            "title": "Nouveau Ticket Critique",
            "message": "Le ticket 'Dégradation des performances sur le cluster Kubernetes' nécessite une escalade N3.",
            "status": "SENT",
            "days_ago": 0.6,
        },
        {
            "user_id": admin_user_id,
            "channel": "SMS",
            "title": "Alerte SLA Dépassé",
            "message": "Le ticket #TICK-1031 'Panne persistante du scanner réseau' a franchi sa date limite de résolution.",
            "status": "SENT",
            "days_ago": 2,
        },
        {
            "user_id": str(user_map["sophie.laurent@geiser.com"]),
            "channel": "IN_APP",
            "title": "Ticket Résolu",
            "message": "Votre demande 'Batterie déformée et surchauffe sur Dell' a été résolue par Ines Kefi.",
            "status": "SENT",
            "days_ago": 8,
        },
        {
            "user_id": str(user_map["sophie.laurent@geiser.com"]),
            "channel": "EMAIL",
            "title": "Confirmation de satisfaction",
            "message": "Merci d'avoir évalué notre intervention (5/5). Votre avis compte pour nous.",
            "status": "SENT",
            "days_ago": 7.9,
        },
        {
            "user_id": str(user_map["eleonore.dupont@geiser.com"]),
            "channel": "IN_APP",
            "title": "Ticket Assigné",
            "message": "Votre ticket 'Bourrage papier HP LaserJet' est pris en charge par Mohamed Jlassi.",
            "status": "SENT",
            "days_ago": 1.2,
        },
        {
            "user_id": str(user_map["antoine.lefebvre@geiser.com"]),
            "channel": "EMAIL",
            "title": "Ticket Résolu",
            "message": "Le profil Outlook corrompu a été restauré par Adam Chemengui.",
            "status": "SENT",
            "days_ago": 5,
        },
        {
            "user_id": str(user_map["thomas.legrand@geiser.com"]),
            "channel": "IN_APP",
            "title": "Alerte Risque SLA",
            "message": "Le ticket 'Lenteur VPN site distant de Lyon' est sous surveillance renforcée.",
            "status": "SENT",
            "days_ago": 1.5,
        },
    ]

    for n in notifications_data:
        doc = {
            "user_id": n["user_id"],
            "channel": n["channel"],
            "title": n["title"],
            "message": n["message"],
            "status": n["status"],
            "created_at": now - timedelta(days=n["days_ago"]),
        }
        await db.notifications.insert_one(doc)

    print(f"  Inserted {len(notifications_data)} notifications.")

    # ─────────────────────────────────────────────────────────────────────────
    # 6. SLA ALERTS
    # ─────────────────────────────────────────────────────────────────────────
    print("\n--- Seeding SLA Alerts ---")

    sla_alerts_data = [
        {
            "ticket_id": str(inserted_ticket_ids[0]),
            "subject": "Saturation de la bande passante sur la liaison fibre principale",
            "priority": "URGENT",
            "sla_status": "ON_TRACK",
            "sla_deadline": now + timedelta(hours=2.5),
            "time_remaining_minutes": 150,
            "assigned_agent_id": str(agent_id_map["ahmed.trabelsi"]),
            "created_at": now - timedelta(hours=1),
        },
        {
            "ticket_id": str(inserted_ticket_ids[3]),
            "subject": "Impossible de joindre le sous-réseau DMZ recette depuis le VPN",
            "priority": "HIGH",
            "sla_status": "AT_RISK",
            "sla_deadline": now + timedelta(minutes=45),
            "time_remaining_minutes": 45,
            "assigned_agent_id": None,
            "created_at": now - timedelta(hours=7),
        },
        {
            "ticket_id": str(inserted_ticket_ids[-2]),
            "subject": "Lenteur extrême d'accès aux disques réseau depuis le site distant de Lyon",
            "priority": "HIGH",
            "sla_status": "BREACHED",
            "sla_deadline": now - timedelta(hours=6),
            "time_remaining_minutes": 0,
            "assigned_agent_id": None,
            "created_at": now - timedelta(hours=6),
        },
        {
            "ticket_id": str(inserted_ticket_ids[-3]),
            "subject": "Panne persistante du scanner réseau Bâtiment C",
            "priority": "MEDIUM",
            "sla_status": "BREACHED",
            "sla_deadline": now - timedelta(days=2),
            "time_remaining_minutes": 0,
            "assigned_agent_id": str(agent_id_map["mohamed.jlassi"]),
            "created_at": now - timedelta(days=2),
        },
    ]

    for alert in sla_alerts_data:
        await db.sla_alerts.insert_one(alert)

    print(f"  Inserted {len(sla_alerts_data)} SLA alerts.")

    # Summary counts
    total_u = await db.users.count_documents({})
    total_t = await db.tickets.count_documents({})
    total_ag = await db.agents.count_documents({})
    total_tm = await db.teams.count_documents({})
    total_notif = await db.notifications.count_documents({})
    print("\n========================================================")
    print("  DATABASE SEEDING SUCCESSFUL!")
    print(f"  Users:         {total_u}")
    print(f"  Agents:        {total_ag}")
    print(f"  Teams:         {total_tm}")
    print(f"  Tickets:       {total_t}")
    print(f"  Notifications: {total_notif}")
    print("========================================================\n")


if __name__ == "__main__":
    asyncio.run(seed_database())
