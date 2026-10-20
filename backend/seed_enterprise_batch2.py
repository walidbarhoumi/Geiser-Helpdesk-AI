r"""
GEISER ITSM - Seed Enterprise Data Batch 2
Adds 15 new users + 35 new richly-described tickets to MongoDB.
Run from: c:\Users\bwali\Documents\geiser\backend\
    python seed_enterprise_batch2.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
import random
from pymongo import MongoClient
from bson import ObjectId
from core.security import get_password_hash

# ── DB ────────────────────────────────────────────────────────────────────────
client = MongoClient("mongodb://localhost:27017")
db = client["itsm_helpdesk"]

NOW = datetime.utcnow()

def dt(days_ago=0, hours_ago=0):
    return NOW - timedelta(days=days_ago, hours=hours_ago)

# ── Fetch existing agents ──────────────────────────────────────────────────────
agents = list(db.agents.find({}, {"_id": 1, "user_id": 1}))
agent_ids = [str(a["_id"]) for a in agents]

def pick_agent():
    return random.choice(agent_ids) if agent_ids else None

# ── 1. NEW USERS ──────────────────────────────────────────────────────────────
hashed_pw = get_password_hash("Password123!")

new_users = [
    # Production
    {
        "email": "rania.tlili@geiser.com",
        "full_name": "Rania Tlili",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Production",
        "phone": "+216 71 456 781",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(60),
        "updated_at": dt(60),
    },
    {
        "email": "sami.bouazizi@geiser.com",
        "full_name": "Sami Bouazizi",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Production",
        "phone": "+216 71 456 782",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(58),
        "updated_at": dt(58),
    },
    # Achats & Approvisionnement
    {
        "email": "lea.martin@geiser.com",
        "full_name": "Léa Martin",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Achats & Approvisionnement",
        "phone": "+33 1 45 67 89 12",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(55),
        "updated_at": dt(55),
    },
    {
        "email": "nicolas.petit@geiser.com",
        "full_name": "Nicolas Petit",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Achats & Approvisionnement",
        "phone": "+33 1 45 67 89 13",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(54),
        "updated_at": dt(54),
    },
    # Marketing Digital
    {
        "email": "inès.belhaj@geiser.com",
        "full_name": "Inès Belhaj",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Marketing Digital",
        "phone": "+216 71 456 783",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(50),
        "updated_at": dt(50),
    },
    {
        "email": "victor.morel@geiser.com",
        "full_name": "Victor Morel",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Marketing Digital",
        "phone": "+33 1 45 67 89 14",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(49),
        "updated_at": dt(49),
    },
    # Communication Interne
    {
        "email": "clara.simon@geiser.com",
        "full_name": "Clara Simon",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Communication Interne",
        "phone": "+33 1 45 67 89 15",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(47),
        "updated_at": dt(47),
    },
    # Service Clients
    {
        "email": "mehdi.ben_salah@geiser.com",
        "full_name": "Mehdi Ben Salah",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Service Clients",
        "phone": "+216 71 456 784",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(45),
        "updated_at": dt(45),
    },
    {
        "email": "pauline.girard@geiser.com",
        "full_name": "Pauline Girard",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Service Clients",
        "phone": "+33 1 45 67 89 16",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(44),
        "updated_at": dt(44),
    },
    # Audit & Compliance
    {
        "email": "farouk.gharbi@geiser.com",
        "full_name": "Farouk Gharbi",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Audit & Compliance",
        "phone": "+216 71 456 785",
        "is_active": True,
        "two_factor_enabled": True,
        "created_at": dt(42),
        "updated_at": dt(42),
    },
    # Management de Projet
    {
        "email": "alice.dupuis@geiser.com",
        "full_name": "Alice Dupuis",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Management de Projet",
        "phone": "+33 1 45 67 89 17",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(40),
        "updated_at": dt(40),
    },
    {
        "email": "karim.laabidi@geiser.com",
        "full_name": "Karim Laabidi",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Management de Projet",
        "phone": "+216 71 456 786",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(39),
        "updated_at": dt(39),
    },
    # Data & Analytics
    {
        "email": "emma.leroy@geiser.com",
        "full_name": "Emma Leroy",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Data & Analytics",
        "phone": "+33 1 45 67 89 18",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(37),
        "updated_at": dt(37),
    },
    {
        "email": "bilel.aouini@geiser.com",
        "full_name": "Bilel Aouini",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Data & Analytics",
        "phone": "+216 71 456 787",
        "is_active": True,
        "two_factor_enabled": False,
        "created_at": dt(36),
        "updated_at": dt(36),
    },
    # Direction Générale
    {
        "email": "yasmine.hammami@geiser.com",
        "full_name": "Yasmine Hammami",
        "hashed_password": hashed_pw,
        "role": "USER",
        "department": "Direction Générale",
        "phone": "+216 71 456 788",
        "is_active": True,
        "two_factor_enabled": True,
        "created_at": dt(35),
        "updated_at": dt(35),
    },
]

# Insert users (idempotent by email)
user_id_map = {}
inserted_users = 0
for u in new_users:
    existing = db.users.find_one({"email": u["email"]})
    if existing:
        user_id_map[u["email"]] = str(existing["_id"])
        print(f"  [SKIP user] {u['email']} already exists")
    else:
        result = db.users.insert_one(u)
        user_id_map[u["email"]] = str(result.inserted_id)
        inserted_users += 1
        print(f"  [+user] {u['full_name']} ({u['department']})")

print(f"\n[OK] Users: {inserted_users} inserted, {len(new_users) - inserted_users} already existed\n")

# Map email → user_id for tickets
def uid(email):
    found = db.users.find_one({"email": email})
    return str(found["_id"]) if found else None

# ── 2. NEW TICKETS ─────────────────────────────────────────────────────────────
def make_ticket(subject, description, category, subcategory, priority,
                status, user_email, days_ago_created,
                resolution_note=None, csat_rating=None, csat_comment=None,
                sla_status="ON_TRACK", hours_ago_updated=0,
                tags=None):

    user_id = uid(user_email)
    agent_id = pick_agent()
    now_c = dt(days_ago_created)
    now_u = dt(hours_ago=hours_ago_updated) if hours_ago_updated else dt(days_ago_created - 1)

    sla_hours = {"LOW": 72, "MEDIUM": 24, "HIGH": 8, "URGENT": 4}[priority]
    sla_due = now_c + timedelta(hours=sla_hours)

    resolved_at = None
    closed_at = None
    if status in ("RESOLVED", "CLOSED"):
        resolved_at = now_c + timedelta(hours=random.randint(2, sla_hours - 1))
        if status == "CLOSED":
            closed_at = resolved_at + timedelta(hours=random.randint(1, 12))

    csat_submitted_at = (resolved_at + timedelta(hours=random.randint(1, 48))) if (csat_rating and resolved_at) else None

    return {
        "subject": subject,
        "description": description,
        "category": category,
        "subcategory": subcategory,
        "status": status,
        "priority": priority,
        "impact": random.choice(["LOW", "MEDIUM", "HIGH"]),
        "urgency": random.choice(["LOW", "MEDIUM", "HIGH"]),
        "priority_source": random.choice(["MANUAL", "AI", "ITIL_MATRIX"]),
        "channel": random.choice(["WEB", "EMAIL", "CHAT"]),
        "user_id": user_id,
        "agent_id": agent_id,
        "team_id": None,
        "tags": tags or [],
        "resolution_note": resolution_note,
        "satisfaction_rating": csat_rating,
        "satisfaction_comment": csat_comment,
        "satisfaction_submitted_at": csat_submitted_at,
        "sla_due_at": sla_due,
        "sla_status": sla_status,
        "resolved_at": resolved_at,
        "closed_at": closed_at,
        "created_at": now_c,
        "updated_at": now_u,
        "first_response_at": now_c + timedelta(minutes=random.randint(5, 45)),
        "ai_category": category,
        "ai_subcategory": subcategory,
        "ai_priority": priority,
        "ai_confidence": round(random.uniform(0.78, 0.99), 2),
        "ai_summary": f"Demande {category.lower()} — {subcategory.lower()}",
        "attachments": [],
        "comments": [],
        "history": [],
    }


tickets_to_add = [

    # ──────────────────────── RESOLVED (12) ───────────────────────────────────

    make_ticket(
        subject="SharePoint Online : Impossible d'accéder au site projet 'Plan Industriel 2025'",
        description=(
            "Depuis ce matin (08h30), je n'arrive plus à ouvrir le site SharePoint dédié au projet "
            "'Plan Industriel 2025'. Le navigateur affiche l'erreur : 'Accès refusé - Code HTTP 403'. "
            "J'ai pourtant été ajoutée comme contributrice la semaine dernière par mon manager. "
            "Collègues du même projet : même problème. Navigateurs testés : Edge 121, Chrome 122. "
            "URL du site : https://geiser.sharepoint.com/sites/PlanIndus2025. Urgent car réunion de revue ce soir."
        ),
        category="Logiciels & Applications",
        subcategory="ERP & Outils Métier",
        priority="HIGH",
        status="RESOLVED",
        user_email="rania.tlili@geiser.com",
        days_ago_created=14,
        resolution_note=(
            "La synchronisation des groupes Azure AD vers SharePoint Online avait un délai de replication > 24h "
            "suite à une migration de tenant partielle. Les permissions ont été réappliquées manuellement via "
            "l'interface d'administration SharePoint. Tous les membres du groupe 'PlanIndus2025-Contrib' ont "
            "désormais accès. Un script PowerShell de vérification de synchronisation AAD a été planifié."
        ),
        csat_rating=5,
        csat_comment="Résolution rapide et explication claire du problème. Merci !",
        sla_status="COMPLETED",
        tags=["sharepoint", "azure-ad", "permissions"],
    ),

    make_ticket(
        subject="OneDrive Entreprise : fichiers en conflit '.conflict' sur le poste de Nicolas Petit",
        description=(
            "Depuis la mise à jour du client OneDrive vers la version 23.246.1126, plusieurs fichiers "
            "Excel et Word de mon dossier 'Appels d'Offres 2024' apparaissent en double avec le suffixe "
            "'.conflict-NomOrdinateur'. Le fichier 'AO_Fournisseur_Acier_v4.xlsx' a 3 copies conflictuelles. "
            "La synchronisation est bloquée (icône rouge dans la barre des tâches). "
            "PC : Dell Latitude 5540, Windows 11 Pro 23H2."
        ),
        category="Logiciels & Applications",
        subcategory="Suite Office / Messagerie",
        priority="MEDIUM",
        status="RESOLVED",
        user_email="nicolas.petit@geiser.com",
        days_ago_created=10,
        resolution_note=(
            "Les conflits provenaient d'une synchronisation simultanée sur deux postes avec des versions "
            "différentes du client OneDrive. Procédure appliquée : (1) déconnexion du compte professionnel, "
            "(2) renommage du dossier OneDrive local en OneDrive_backup, (3) reconnexion et re-synchronisation. "
            "Les fichiers en conflit ont été fusionnés manuellement avec l'utilisateur. "
            "Client OneDrive mis à jour vers 24.001 (version stable)."
        ),
        csat_rating=4,
        csat_comment="Problème résolu mais la procédure était longue. Le technicien a été très patient.",
        sla_status="COMPLETED",
        tags=["onedrive", "sync", "conflit-fichier"],
    ),

    make_ticket(
        subject="Renouvellement certificat SSL/TLS VPN concentrateur ASA 5525-X — expiration J-3",
        description=(
            "Le certificat SSL du concentrateur VPN Cisco ASA 5525-X (IP : 10.0.1.1) arrive à expiration "
            "dans 3 jours (le 15/01/2025). Les utilisateurs voient déjà l'avertissement de sécurité dans "
            "AnyConnect. Le certificat actuel a été émis par notre PKI interne (CA : GEISER-ROOT-CA). "
            "CN=vpn.geiser.com, Serial: 2B:4F:9A:... , SHA256. "
            "Renouvellement urgent requis pour éviter l'interruption d'accès VPN pour ~200 utilisateurs distants."
        ),
        category="Infrastructure & Réseau",
        subcategory="VPN & Accès Distant",
        priority="URGENT",
        status="RESOLVED",
        user_email="farouk.gharbi@geiser.com",
        days_ago_created=18,
        resolution_note=(
            "CSR généré sur le concentrateur ASA via ASDM, soumis à la CA interne GEISER-ROOT-CA. "
            "Nouveau certificat (validité 2 ans, SHA-256, SAN : vpn.geiser.com / vpn-backup.geiser.com) "
            "importé et activé sur l'interface outside. Redémarrage du service SSL sans interruption de service "
            "(mode maintenance de 2 min à 22h00). Tous les clients AnyConnect reconnectés sans avertissement. "
            "Entrée de calendrier créée pour J-30 avant la prochaine expiration (janvier 2027)."
        ),
        csat_rating=5,
        csat_comment="Intervention parfaite, zéro coupure pour les utilisateurs. Très professionnel.",
        sla_status="COMPLETED",
        tags=["vpn", "ssl", "certificat", "cisco-asa"],
    ),

    make_ticket(
        subject="Imprimante HP Color LaserJet MFP E77825 non visible après migration VLAN Finance",
        description=(
            "Suite à la migration du VLAN Finance (ancien VLAN 20 → nouveau VLAN 45, sous-réseau 192.168.45.0/24), "
            "l'imprimante réseau HP Color LaserJet MFP E77825 (MAC: AC:16:2D:44:7B:9F, ancienne IP: 192.168.20.34) "
            "n'est plus détectable depuis les postes du service Finance. "
            "L'imprimante est physiquement connectée au switch Cisco Catalyst 2960-X port Gi0/12. "
            "HP Web Jetadmin ne la trouve plus. Impossible de réimprimer les relevés mensuels."
        ),
        category="Matériel & Poste de Travail",
        subcategory="Imprimante & Scanner",
        priority="HIGH",
        status="RESOLVED",
        user_email="sophie.laurent@geiser.com",
        days_ago_created=8,
        resolution_note=(
            "Le port du switch Gi0/12 n'avait pas été migré vers le nouveau VLAN 45. "
            "Configuration appliquée : 'switchport access vlan 45' sur le port concerné. "
            "Nouvelle IP attribuée via réservation DHCP : 192.168.45.34 (MAC liée). "
            "Mise à jour des pilotes HP sur tous les postes Finance via GPO (HP Universal Print Driver 7.1). "
            "File d'impression purgée et testée — 5 pages de test imprimées avec succès."
        ),
        csat_rating=5,
        csat_comment="Résolu en moins de 2 heures, impeccable !",
        sla_status="COMPLETED",
        tags=["imprimante", "hp", "vlan", "cisco"],
    ),

    make_ticket(
        subject="Tentative de phishing SMS ciblant les identifiants Salesforce — équipe Service Clients",
        description=(
            "Plusieurs collaborateurs du Service Clients (dont moi) ont reçu ce matin des SMS frauduleux "
            "se faisant passer pour Salesforce Support : 'Votre session Salesforce a expiré. "
            "Reconnectez-vous : https://salesf0rce-secure-login[.]com'. "
            "Au moins 2 collègues (Pauline Girard, Mehdi Ben Salah) ont cliqué sur le lien et saisi leurs identifiants. "
            "Numéro expéditeur : +44 7700 123456. Signalement immédiat à la sécurité requis."
        ),
        category="Sécurité IT",
        subcategory="Email Suspect / Phishing",
        priority="URGENT",
        status="RESOLVED",
        user_email="mehdi.ben_salah@geiser.com",
        days_ago_created=5,
        resolution_note=(
            "Incident de sécurité traité en urgence : (1) Réinitialisation forcée des mots de passe Salesforce "
            "des 2 comptes compromis (Girard + Ben Salah). (2) Activation temporaire du blocage de session sur "
            "les 2 comptes dans Salesforce Shield. (3) Revue des logs Salesforce Event Monitoring — aucun accès "
            "non autorisé détecté avant la réinitialisation. (4) Sensibilisation flash envoyée à toute l'équipe SC. "
            "(5) Numéro bloqué via l'opérateur télécom. Rapport ISO 27001 SOC créé. Clôturé sans exfiltration confirmée."
        ),
        csat_rating=4,
        csat_comment="Réaction rapide de l'équipe sécu. Communication rassurante.",
        sla_status="COMPLETED",
        tags=["phishing", "sms", "salesforce", "securite", "iso27001"],
    ),

    make_ticket(
        subject="Mise à jour Windows 11 23H2 bloquée — erreur 0x80070057 sur 12 postes production",
        description=(
            "Depuis le déploiement automatique de la mise à jour cumulatives KB5034123 (Windows 11 23H2) "
            "via WSUS, 12 postes du service Production sont bloqués avec l'erreur 0x80070057 "
            "('Le paramètre est incorrect') pendant la phase 'Configuration de Windows'. "
            "Les postes redémarrent en boucle et reviennent à Windows 11 22H2. "
            "Modèles affectés : Dell OptiPlex 7090 (7 postes), HP EliteDesk 800 G9 (5 postes). "
            "Logs WindowsUpdate.log disponibles sur partage \\\\FS-SUPPORT\\logs\\wu."
        ),
        category="Logiciels & Applications",
        subcategory="Installation & Mise à jour",
        priority="HIGH",
        status="RESOLVED",
        user_email="rania.tlili@geiser.com",
        days_ago_created=12,
        resolution_note=(
            "L'erreur 0x80070057 était causée par une corruption de la partition de récupération (trop petite, < 700 MB) "
            "suite à un redimensionnement de partition précédent. Solution déployée via script PowerShell centralisé : "
            "(1) Extension de la partition de récupération à 1 GB, (2) Mise à jour forcée via 'wusa.exe' avec flag "
            "/quiet /norestart, (3) Redémarrage planifié à 21h00. "
            "12/12 postes mis à jour avec succès. KB5034123 validée sur tous. "
            "Script archivé dans le référentiel PowerShell DSC pour futurs déploiements."
        ),
        csat_rating=5,
        csat_comment="Résolution impeccable, tous nos postes sont à jour maintenant.",
        sla_status="COMPLETED",
        tags=["windows11", "wsus", "mise-a-jour", "0x80070057"],
    ),

    make_ticket(
        subject="Accès refusé au dépôt GitLab après rotation des tokens OAuth2 d'intégration CI/CD",
        description=(
            "Suite à la rotation planifiée des tokens OAuth2 du groupe GitLab 'geiser-rd' (rotation effectuée "
            "le 08/01 à 14h00), nos pipelines CI/CD GitLab Runner se terminent en erreur : "
            "'remote: HTTP Basic: Access denied. The provided password or token is incorrect.' "
            "Les runners concernés : gitlab-runner-prod-01, gitlab-runner-prod-02 (tags: docker, linux). "
            "Projet impacté : 14 pipelines bloqués dont 3 déploiements en attente (API, Frontend, Mobile). "
            "Accès aux dépôts via interface web OK."
        ),
        category="Authentification & Accès",
        subcategory="Déverrouillage de Compte",
        priority="URGENT",
        status="RESOLVED",
        user_email="bilel.aouini@geiser.com",
        days_ago_created=7,
        resolution_note=(
            "Les variables CI/CD GitLab stockant les anciens tokens n'avaient pas été mises à jour après la rotation. "
            "Actions réalisées : (1) Génération d'un nouveau Project Access Token (scope: read_repository, write_repository) "
            "dans Paramètres > Tokens d'accès. (2) Mise à jour de la variable CI/CD 'CI_REGISTRY_TOKEN' dans les settings "
            "des 14 projets impactés (automatisé via API GitLab + script Python). "
            "(3) Relance manuelle des 3 pipelines de déploiement — succès. "
            "Documentation de la procédure de rotation ajoutée au Confluence DSI."
        ),
        csat_rating=5,
        csat_comment="Super, les pipelines tournent à nouveau. Merci pour la rapidité !",
        sla_status="COMPLETED",
        tags=["gitlab", "ci-cd", "oauth2", "token-rotation"],
    ),

    make_ticket(
        subject="Crash répété Jupyter Notebook — KernelDied avec erreur SIGKILL dans l'environnement Conda",
        description=(
            "L'application Jupyter Notebook 7.0.6 (environnement Conda 'geiser-ds-env') plante "
            "systématiquement lors de l'exécution de cellules utilisant pandas (>1M lignes) ou PyTorch. "
            "Erreur : 'The kernel appears to have died. It will restart automatically.' "
            "Suivi par '[KernelDied] The kernel died with error code 137 (SIGKILL)'. "
            "Système : macOS Sonoma 14.2, MacBook Pro M2 Pro 16GB RAM. "
            "La même cellule fonctionne sur le serveur Jupyter du cluster (192.168.10.50)."
        ),
        category="Logiciels & Applications",
        subcategory="ERP & Outils Métier",
        priority="MEDIUM",
        status="RESOLVED",
        user_email="emma.leroy@geiser.com",
        days_ago_created=9,
        resolution_note=(
            "Le noyau Python était tué par macOS par OOM (Out-Of-Memory) malgré les 16GB RAM, "
            "car l'environnement Conda utilisait la gestion mémoire de pandad par défaut (copy-on-write désactivé). "
            "Solution : (1) Activation de pandas 2.0 CoW : pd.options.mode.copy_on_write = True. "
            "(2) Ajout de chunking sur les DataFrames lourds. (3) Limite mémoire Jupyter ajustée "
            "dans jupyter_notebook_config.py : c.NotebookApp.max_buffer_size = 8589934592. "
            "Tests validés — kernels stables sur datasets 5M lignes."
        ),
        csat_rating=4,
        csat_comment="Merci, j'ai appris quelque chose sur la gestion mémoire pandas. Très utile !",
        sla_status="COMPLETED",
        tags=["jupyter", "python", "conda", "macos", "oom"],
    ),

    make_ticket(
        subject="Compte Active Directory verrouillé après tentatives de connexion RDP échouées — Farouk Gharbi",
        description=(
            "Mon compte AD (fgharbi@geiser.local) a été verrouillé automatiquement ce matin à 07h42. "
            "Je n'ai pas réussi à me connecter en RDP depuis mon domicile (VPN actif). "
            "L'observateur d'événements du contrôleur de domaine (DC-PROD-01) indique "
            "28 tentatives de connexion RDP échouées depuis l'IP 10.10.5.28 (mon poste VPN). "
            "Poste VPN : HP EliteBook 840 G10. La politique de verrouillage : 5 tentatives / 15 min."
        ),
        category="Authentification & Accès",
        subcategory="Déverrouillage de Compte",
        priority="HIGH",
        status="RESOLVED",
        user_email="farouk.gharbi@geiser.com",
        days_ago_created=6,
        resolution_note=(
            "Compte AD déverrouillé manuellement via Active Directory Users & Computers (ADUC) sur DC-PROD-01. "
            "Analyse des logs : les tentatives provenaient du credential manager Windows qui avait mis en cache "
            "un ancien mot de passe. Procédure appliquée avec l'utilisateur : "
            "(1) Suppression des credentials cachés dans Gestionnaire de credentials Windows. "
            "(2) Réinitialisation du mot de passe AD (conformément à la politique 12 chars, complexité). "
            "(3) Test de connexion RDP validé. Recommandation : activer Windows Hello Entreprise pour éviter ce type de blocage."
        ),
        csat_rating=5,
        csat_comment="Débloqué en 10 minutes, parfait !",
        sla_status="COMPLETED",
        tags=["active-directory", "rdp", "verrouillage", "vpn"],
    ),

    make_ticket(
        subject="Demande d'accès à l'outil de BI Power BI Premium pour l'équipe Data & Analytics",
        description=(
            "L'équipe Data & Analytics (4 personnes : Emma Leroy, Bilel Aouini, et 2 stagiaires) "
            "a besoin d'accès à Power BI Premium (workspace 'Analyses Stratégiques GEISER'). "
            "Actuellement, nous n'avons que des licences Power BI Pro qui ne permettent pas "
            "d'accéder aux rapports paginés ni aux flux de données (dataflows) du workspace Premium. "
            "Besoin validé par notre responsable (Marie-Claire Fontaine) par email le 05/01."
        ),
        category="Logiciels & Applications",
        subcategory="ERP & Outils Métier",
        priority="MEDIUM",
        status="RESOLVED",
        user_email="emma.leroy@geiser.com",
        days_ago_created=11,
        resolution_note=(
            "Licences Power BI Premium Per User (PPU) attribuées aux 4 membres de l'équipe Data & Analytics "
            "via le portail Microsoft 365 Admin Center. "
            "Droits d'accès ajoutés sur le workspace 'Analyses Stratégiques GEISER' (rôle : Contributeur). "
            "Test d'accès validé pour tous les membres. "
            "Facture mensuelle supplémentaire : 4 × 20€ = 80€/mois — validé par la DSI."
        ),
        csat_rating=4,
        csat_comment="Merci, nous avons maintenant accès à tous les rapports dont nous avions besoin.",
        sla_status="COMPLETED",
        tags=["power-bi", "licence", "microsoft365", "analytics"],
    ),

    make_ticket(
        subject="Écran externe Dell U2722D non reconnu sur station d'accueil Thunderbolt — macOS Ventura",
        description=(
            "Mon écran externe Dell UltraSharp U2722D (connexion USB-C / Thunderbolt 4) n'est plus reconnu "
            "après la mise à jour macOS vers Ventura 13.6.3 (22G436). "
            "L'écran était fonctionnel sous Monterey. Via la station d'accueil CalDigit TS4. "
            "La sortie HDMI directe depuis le MacBook fonctionne. "
            "Poste : MacBook Pro 14' M1 Pro. Commandes testées : 'system_profiler SPDisplaysDataType' — "
            "l'écran n'apparaît pas. Redémarrage NVRAM/SMC effectués sans succès."
        ),
        category="Matériel & Poste de Travail",
        subcategory="Écran & Périphériques",
        priority="MEDIUM",
        status="RESOLVED",
        user_email="alice.dupuis@geiser.com",
        days_ago_created=13,
        resolution_note=(
            "Le problème était un conflit entre le firmware de la station d'accueil CalDigit TS4 (version 4.0.1) "
            "et macOS Ventura 13.6.3. Solution : "
            "(1) Mise à jour du firmware CalDigit TS4 vers 4.2.0 via l'application CalDigit Firmware. "
            "(2) Réinitialisation des paramètres SMC. "
            "(3) Reconnexion de l'écran — détecté immédiatement en 4K@60Hz. "
            "Bugfix CalDigit référencé : TSB-2024-012. Mise à jour recommandée à tous les utilisateurs CalDigit."
        ),
        csat_rating=5,
        csat_comment="Parfait ! L'écran fonctionne à nouveau normalement, merci.",
        sla_status="COMPLETED",
        tags=["ecran", "thunderbolt", "macos", "caldigit", "dell"],
    ),

    make_ticket(
        subject="Récupération d'emails supprimés définitivement dans Outlook Exchange — boîte Thomas Legrand",
        description=(
            "J'ai vidé ma corbeille Outlook par erreur ce matin (CTRL+A puis Suppr dans la corbeille). "
            "Parmi les emails supprimés, il y avait une chaîne de 47 messages avec notre client Grands Comptes "
            "'Airbus Group' concernant le contrat Q1 2025 (valeur ~2M€). "
            "Suppression effectuée à 09h17. Serveur Exchange Online (Microsoft 365 E3). "
            "Délai de rétention des éléments supprimés : 30 jours (selon politique DLP)."
        ),
        category="Logiciels & Applications",
        subcategory="Suite Office / Messagerie",
        priority="URGENT",
        status="RESOLVED",
        user_email="thomas.legrand@geiser.com",
        days_ago_created=3,
        resolution_note=(
            "Récupération effectuée via Exchange Admin Center > Boîtes aux lettres > Récupérer les éléments supprimés. "
            "Les 47 emails de la chaîne Airbus Group ont été restaurés dans un dossier 'Éléments restaurés 09/01' "
            "dans la boîte de Thomas Legrand. Restauration en < 30 min après le signalement. "
            "Recommandation transmise : activer le dossier Archive Online (auto-expand) et la stratégie MRM. "
            "Sensibilisation à l'utilisation du dossier Archive plutôt que la suppression définitive."
        ),
        csat_rating=5,
        csat_comment="Incroyable ! Tous mes emails ont été récupérés. Vous m'avez sauvé !",
        sla_status="COMPLETED",
        tags=["exchange", "outlook", "restauration", "email", "microsoft365"],
    ),

    # ──────────────────────── IN_PROGRESS (10) ────────────────────────────────

    make_ticket(
        subject="Alerte critique disque sur serveur de fichiers FS-PROD-01 — partition /data à 97%",
        description=(
            "L'outil de supervision Zabbix (dashboard.geiser.internal) remonte une alerte critique : "
            "la partition /data du serveur FS-PROD-01 (Ubuntu 22.04 LTS, DELL PowerEdge R750) est à 97% "
            "de capacité utilisée (9.7 TB / 10 TB). "
            "Ce serveur héberge les partages CIFS des équipes Production et R&D. "
            "Croissance du stockage ce mois : +1.2 TB en 30 jours (forte activité CAD/CAM). "
            "Risque d'indisponibilité du stockage dans < 48h si aucune action."
        ),
        category="Infrastructure & Réseau",
        subcategory="Serveurs & Cloud",
        priority="URGENT",
        status="IN_PROGRESS",
        user_email="rania.tlili@geiser.com",
        days_ago_created=2,
        sla_status="AT_RISK",
        tags=["serveur", "stockage", "zabbix", "fs-prod-01", "critique"],
    ),

    make_ticket(
        subject="Déploiement Kubernetes : pods du service 'invoice-api' en CrashLoopBackOff après release v2.4",
        description=(
            "Suite au déploiement de la release v2.4 du microservice 'invoice-api' sur le cluster Kubernetes "
            "de production (namespace: geiser-prod), 3 pods sur 3 sont en état CrashLoopBackOff. "
            "Logs kubectl : 'Error: connect ECONNREFUSED 10.96.0.1:5432 — Connection to PostgreSQL refused'. "
            "La base PostgreSQL 'invoice_db' est accessible depuis les autres namespaces. "
            "ConfigMap 'invoice-api-config' pointait sur l'URL de staging. "
            "Rollback v2.3 effectué mais le service doit être en v2.4 pour la facturation du mois."
        ),
        category="Infrastructure & Réseau",
        subcategory="Serveurs & Cloud",
        priority="URGENT",
        status="IN_PROGRESS",
        user_email="bilel.aouini@geiser.com",
        days_ago_created=1,
        sla_status="AT_RISK",
        tags=["kubernetes", "docker", "postgresql", "microservices", "devops"],
    ),

    make_ticket(
        subject="Demande d'onboarding IT pour 5 nouvelles recrues du département Marketing Digital",
        description=(
            "Suite aux recrutements validés en janvier 2025, 5 nouveaux collaborateurs rejoignent "
            "le département Marketing Digital le 20/01/2025 : "
            "1. Sarah Khalil (Chef de projet SEO), 2. Maxime Aubert (Développeur front-end), "
            "3. Camille Renard (Data analyst marketing), 4. Léa Fontaine (Social media manager), "
            "5. Yacine Bouzid (UX/UI designer). "
            "Besoins : comptes AD, emails @geiser.com, postes de travail (4 Mac + 1 PC), "
            "accès Google Analytics 4, Meta Business Suite, HubSpot CRM, Figma, Adobe CC."
        ),
        category="Support Général",
        subcategory="Autre Demande",
        priority="HIGH",
        status="IN_PROGRESS",
        user_email="inès.belhaj@geiser.com",
        days_ago_created=4,
        sla_status="ON_TRACK",
        tags=["onboarding", "rh", "nouveaux-comptes", "adobe-cc", "hubspot"],
    ),

    make_ticket(
        subject="Latence anormale sur le réseau Wi-Fi du bâtiment B — salle de réunion 3e étage",
        description=(
            "Depuis lundi 06/01, les salles de réunion du 3e étage du bâtiment B souffrent de latences "
            "Wi-Fi très élevées (ping > 400ms, perte de paquets 15-30%) rendant Teams et Zoom inutilisables. "
            "Point d'accès concerné : AP-BATB-3F-04 (Cisco Catalyst 9130AX, IP: 192.168.12.44). "
            "Les autres AP du même étage (AP-BATB-3F-01 à 03) sont normaux. "
            "Réunions clients impactées : 3 déjà perturbées cette semaine. "
            "Signalement confirmé par 8 utilisateurs différents."
        ),
        category="Infrastructure & Réseau",
        subcategory="Connexion Wi-Fi / Filaire",
        priority="HIGH",
        status="IN_PROGRESS",
        user_email="clara.simon@geiser.com",
        days_ago_created=4,
        sla_status="ON_TRACK",
        tags=["wifi", "cisco", "latence", "teams", "batiment-b"],
    ),

    make_ticket(
        subject="Erreur de synchronisation SAP ERP — module MM non disponible depuis la mise à jour SP15",
        description=(
            "Depuis l'application du Support Package SP15 sur notre instance SAP ERP 6.0 EHP8 (SID: GEP), "
            "le module Materials Management (MM) génère des erreurs ABAP lors de la création de bons de commande : "
            "'DUMP: CALL_FUNCTION_NOT_FOUND — Fonction BAPI_PO_CREATE1 introuvable'. "
            "Erreur visible dans la transaction ST22. "
            "~40 utilisateurs du département Achats bloqués. "
            "Situation : 12 bons de commande urgents en attente (fournisseurs relancent)."
        ),
        category="Logiciels & Applications",
        subcategory="ERP & Outils Métier",
        priority="URGENT",
        status="IN_PROGRESS",
        user_email="lea.martin@geiser.com",
        days_ago_created=2,
        sla_status="BREACHED",
        tags=["sap", "erp", "mm", "abap", "bapi", "achats"],
    ),

    make_ticket(
        subject="Configuration double authentification (2FA) obligatoire — résistance utilisateurs Communication",
        description=(
            "Dans le cadre du renforcement de la politique sécurité ISO 27001 (action plan Q1 2025), "
            "l'activation du 2FA est obligatoire pour tous les comptes @geiser.com d'ici le 31/01/2025. "
            "Le département Communication Interne (8 utilisateurs) signale des difficultés : "
            "3 utilisateurs n'ont pas de smartphone compatible (Authenticator), "
            "2 utilisateurs en télétravail international (numéros non français pour SMS OTP), "
            "Clara Simon bloquée : application Microsoft Authenticator incompatible avec son Android 8.1."
        ),
        category="Authentification & Accès",
        subcategory="Double Facteur (2FA)",
        priority="MEDIUM",
        status="IN_PROGRESS",
        user_email="clara.simon@geiser.com",
        days_ago_created=5,
        sla_status="ON_TRACK",
        tags=["2fa", "mfa", "iso27001", "microsoft-authenticator", "securite"],
    ),

    make_ticket(
        subject="Panne de l'onduleur APC Smart-UPS 3000VA — salle serveurs site Tunis",
        description=(
            "L'onduleur APC Smart-UPS RT 3000VA (SN: AS1734150012) de la salle serveurs du site de Tunis "
            "affiche une alarme rouge constante depuis 14h30. "
            "Beep sonore continu. Écran LCD : 'BATTERY FAULT — Replace battery'. "
            "L'onduleur est en Bypass automatique (réseau EDF direct, sans protection). "
            "Risque : coupure secteur non protégée pour 6 serveurs critiques (DC-TUN-01, DC-TUN-02, "
            "FS-TUN-01, PROXY-TUN-01, MAIL-TUN-01, BACKUP-TUN-01). "
            "Batterie date : 2019 (dépassé 5 ans d'utilisation)."
        ),
        category="Matériel & Poste de Travail",
        subcategory="PC Portable / Fixe",
        priority="URGENT",
        status="IN_PROGRESS",
        user_email="sami.bouazizi@geiser.com",
        days_ago_created=1,
        sla_status="AT_RISK",
        tags=["onduleur", "apc", "ups", "salle-serveurs", "tunis"],
    ),

    make_ticket(
        subject="Migration données CRM Salesforce vers HubSpot — erreurs d'import sur 2300 contacts",
        description=(
            "Dans le cadre du projet de migration CRM (Salesforce → HubSpot Sales Hub Entreprise), "
            "l'import des contacts via fichier CSV échoue pour 2 300 contacts sur 15 000. "
            "Erreur HubSpot Import API : 'INVALID_EMAIL_FORMAT' pour 1 200 contacts, "
            "'DUPLICATE_CONTACT' pour 800 contacts, 'REQUIRED_FIELD_MISSING (phone)' pour 300. "
            "Les 12 700 contacts restants ont été importés avec succès. "
            "Go-live HubSpot prévu le 25/01. Migration critique pour la Direction Commerciale."
        ),
        category="Logiciels & Applications",
        subcategory="ERP & Outils Métier",
        priority="HIGH",
        status="IN_PROGRESS",
        user_email="victor.morel@geiser.com",
        days_ago_created=3,
        sla_status="ON_TRACK",
        tags=["crm", "salesforce", "hubspot", "migration", "data"],
    ),

    make_ticket(
        subject="Poste de travail lent au démarrage — GPO Logon Script bloqué 8 minutes",
        description=(
            "Mon PC (Dell OptiPlex 7010, Windows 10 Pro 22H2) met maintenant plus de 8 minutes "
            "à afficher le bureau après identification. "
            "L'événement 'Applying Group Policy' reste figé pendant 6-7 minutes dans l'interface de chargement. "
            "Depuis 3 jours. Les autres collègues du département (même GPO) n'ont pas le problème. "
            "Domaine : geiser.local. Journal GP : event ID 1085 — 'Erreur de traitement du script de connexion'. "
            "Script de connexion : \\\\geiser.local\\netlogon\\logon.bat"
        ),
        category="Matériel & Poste de Travail",
        subcategory="PC Portable / Fixe",
        priority="MEDIUM",
        status="IN_PROGRESS",
        user_email="karim.laabidi@geiser.com",
        days_ago_created=3,
        sla_status="ON_TRACK",
        tags=["gpo", "active-directory", "logon", "windows10", "performance"],
    ),

    make_ticket(
        subject="Rapport Power BI 'Tableau de bord achats' ne se rafraîchit plus — erreur de source de données",
        description=(
            "Le rapport Power BI Service 'Tableau de bord achats Q1 2025' (workspace Premium 'DSI-Reporting') "
            "n'est plus rafraîchi depuis le 07/01/2025 08h00. "
            "Erreur dans l'historique d'actualisation : 'DataSource.Error: OLE DB or ODBC error: "
            "[Microsoft][ODBC SQL Server Driver][SQL Server]Login failed for user GEISER\\svc_powerbi'. "
            "Le compte de service 'svc_powerbi' a peut-être eu son mot de passe réinitialisé lors "
            "de la rotation trimestrielle des comptes de service (07/01 au soir)."
        ),
        category="Logiciels & Applications",
        subcategory="ERP & Outils Métier",
        priority="HIGH",
        status="IN_PROGRESS",
        user_email="lea.martin@geiser.com",
        days_ago_created=4,
        sla_status="ON_TRACK",
        tags=["power-bi", "sql-server", "compte-service", "odbc", "reporting"],
    ),

    # ──────────────────────── OPEN (7) ────────────────────────────────────────

    make_ticket(
        subject="Demande de création d'une boîte mail partagée — equipe-communication@geiser.com",
        description=(
            "Le département Communication Interne souhaite la création d'une boîte aux lettres partagée "
            "'equipe-communication@geiser.com' sur Exchange Online (Microsoft 365). "
            "Membres devant avoir accès en lecture/écriture : Clara Simon, 2 stagiaires (noms à confirmer). "
            "Besoin : répondre aux demandes internes de création de contenu et aux journalistes. "
            "Quota souhaité : 50 GB. Archivage automatique activé. Calendrier partagé inclus."
        ),
        category="Logiciels & Applications",
        subcategory="Suite Office / Messagerie",
        priority="LOW",
        status="OPEN",
        user_email="clara.simon@geiser.com",
        days_ago_created=2,
        sla_status="ON_TRACK",
        tags=["exchange", "boite-partagee", "microsoft365", "communication"],
    ),

    make_ticket(
        subject="Besoin d'un accès VPN pour prestataire externe — projet audit sécurité GEISER",
        description=(
            "Dans le cadre de l'audit de sécurité ISO 27001 prévu du 20/01 au 07/02/2025, "
            "la société externe 'SecAudit Conseil' (contact : Pierre Alain Moreau, pmoreau@secaudit.fr) "
            "a besoin d'un accès VPN limité au réseau DMZ (192.168.200.0/24) uniquement. "
            "Durée : 18 jours. Comptes à créer : 2 auditeurs. "
            "Restrictions : accès web uniquement, pas d'accès aux serveurs de prod. "
            "Validation sécurité requise avant création du compte."
        ),
        category="Infrastructure & Réseau",
        subcategory="VPN & Accès Distant",
        priority="MEDIUM",
        status="OPEN",
        user_email="farouk.gharbi@geiser.com",
        days_ago_created=1,
        sla_status="ON_TRACK",
        tags=["vpn", "prestataire", "audit", "iso27001", "dmz"],
    ),

    make_ticket(
        subject="Logiciel AutoCAD 2024 — demande de licence supplémentaire pour le service Production",
        description=(
            "Le service Production a actuellement 6 licences AutoCAD 2024 (contrat Autodesk #GEI-2024-AUT-006). "
            "Suite à l'intégration de 2 nouveaux ingénieurs CAO (Karim Laabidi et Sami Bouazizi), "
            "nous avons besoin de 2 licences supplémentaires. "
            "Type de licence souhaitée : Autodesk AutoCAD 2024 + AutoCAD Mechanical (spécialisation). "
            "Devis Autodesk : ~1 800€/an/licence. Validation DSI + Direction nécessaire. "
            "Urgence : les 2 ingénieurs commencent leurs projets CAO le 20/01."
        ),
        category="Logiciels & Applications",
        subcategory="Installation & Mise à jour",
        priority="MEDIUM",
        status="OPEN",
        user_email="sami.bouazizi@geiser.com",
        days_ago_created=2,
        sla_status="ON_TRACK",
        tags=["autocad", "licence", "autodesk", "production", "cad"],
    ),

    make_ticket(
        subject="Alerte sécurité : scan de ports détecté depuis IP interne 192.168.5.234",
        description=(
            "Notre SIEM (Splunk Enterprise 9.1, dashboard Security Operations Center) a déclenché "
            "une alerte de niveau HIGH à 03h22 cette nuit : "
            "un scan de ports Nmap (SYN scan) a été détecté depuis l'IP interne 192.168.5.234 "
            "vers l'ensemble du sous-réseau 192.168.0.0/16 (65 535 ports). "
            "Durée du scan : 47 minutes. 1 247 hôtes scannés. "
            "L'IP 192.168.5.234 est assignée au poste de Mehdi Ben Salah (Service Clients, "
            "PC Dell Latitude 5540, hostname: GEISER-SC-012). "
            "À vérifier : compromission du poste ? Outil de sécurité légitime ?"
        ),
        category="Sécurité IT",
        subcategory="Incident de Sécurité (ISO 27001)",
        priority="URGENT",
        status="OPEN",
        user_email="farouk.gharbi@geiser.com",
        days_ago_created=0,
        sla_status="ON_TRACK",
        tags=["siem", "splunk", "scan-ports", "iso27001", "soc", "incident"],
    ),

    make_ticket(
        subject="Formulaire de demande de congés en ligne inaccessible — app RH 'GRH Portal'",
        description=(
            "L'application interne de gestion RH 'GRH Portal' (https://grh.geiser.internal) "
            "affiche une page d'erreur '502 Bad Gateway' depuis hier 16h30. "
            "Impossible de soumettre les demandes de congés pour la période de février 2025. "
            "La date limite de soumission est le 15/01. "
            "Tentatives depuis : Edge 121, Firefox 123, smartphone. Même résultat. "
            "~180 collaborateurs concernés par cette échéance."
        ),
        category="Logiciels & Applications",
        subcategory="ERP & Outils Métier",
        priority="HIGH",
        status="OPEN",
        user_email="pauline.girard@geiser.com",
        days_ago_created=1,
        sla_status="ON_TRACK",
        tags=["grh", "portail-rh", "conges", "502", "intranet"],
    ),

    make_ticket(
        subject="Demande de migration messagerie Lotus Notes vers Microsoft Outlook — 8 comptes Audit",
        description=(
            "Le département Audit & Compliance utilise encore Lotus Notes (IBM Notes 9.0.1) "
            "pour 8 comptes. Dans le cadre de la modernisation du SI, ces comptes doivent être "
            "migrés vers Microsoft Outlook / Exchange Online (Microsoft 365 E3). "
            "Volume estimé : ~45 000 emails par compte, calendriers + archives locales (.nsf). "
            "Contrainte : les archives doivent être conservées 10 ans (obligation légale audit). "
            "Migration à planifier avant le 31/03/2025. Outil suggéré : Transend Migrator Pro."
        ),
        category="Logiciels & Applications",
        subcategory="Suite Office / Messagerie",
        priority="MEDIUM",
        status="OPEN",
        user_email="farouk.gharbi@geiser.com",
        days_ago_created=3,
        sla_status="ON_TRACK",
        tags=["migration", "lotus-notes", "outlook", "exchange", "audit"],
    ),

    make_ticket(
        subject="Problème de connexion à l'API REST interne depuis les scripts Python du département Data",
        description=(
            "Les scripts Python de collecte de données du département Data & Analytics "
            "ne peuvent plus se connecter à l'API REST interne (https://api.geiser.internal/v2/) "
            "depuis ce matin 07h00. "
            "Erreur : 'ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] "
            "certificate verify failed: unable to get local issuer certificate (_ssl.c:1129)'. "
            "Les scripts utilisent requests 2.31.0 + certifi 2024.01.05. "
            "L'API est accessible via navigateur (certificat vu comme valide). "
            "Hypothèse : rotation du certificat racine CA interne ?"
        ),
        category="Infrastructure & Réseau",
        subcategory="Serveurs & Cloud",
        priority="HIGH",
        status="OPEN",
        user_email="bilel.aouini@geiser.com",
        days_ago_created=0,
        sla_status="ON_TRACK",
        tags=["python", "ssl", "api", "certifi", "ca-interne"],
    ),

    # ──────────────────────── PENDING (4) ─────────────────────────────────────

    make_ticket(
        subject="Installation imprimante de production Zebra ZT411 — étiquetage code-barres GS1",
        description=(
            "Besoin d'installation et configuration de l'imprimante industrielle Zebra ZT411 "
            "(résolution 300 dpi, Ethernet, Bluetooth) pour l'étiquetage code-barres GS1 "
            "dans l'atelier de production. "
            "Logiciel requis : ZebraDesigner Pro 3 + pilotes Windows 10 x64. "
            "L'imprimante sera connectée au switch industriel (VLAN 60 - Production). "
            "Format d'étiquettes : 100×50mm, 2 modèles (produit fini + palette). "
            "Validation des gabarits par le responsable production avant déploiement."
        ),
        category="Matériel & Poste de Travail",
        subcategory="Imprimante & Scanner",
        priority="MEDIUM",
        status="PENDING",
        user_email="sami.bouazizi@geiser.com",
        days_ago_created=6,
        sla_status="PAUSED",
        tags=["zebra", "imprimante", "code-barres", "production", "etiquetage"],
    ),

    make_ticket(
        subject="Renouvellement contrat support Microsoft EA — validation DSI et Direction Financière",
        description=(
            "Le contrat Microsoft Enterprise Agreement (EA #7892341) arrive à renouvellement le 28/02/2025. "
            "Inclus : 350 licences Microsoft 365 E3, Azure subscription, Windows Server CAL. "
            "Microsoft France a transmis le devis de renouvellement (3 ans) : 487 000€ HT. "
            "Points à négocier : ajout de 20 licences Defender for Endpoint, suppression de 15 "
            "licences Project Online non utilisées. "
            "En attente de validation : DSI (Claire Dubois) + Direction Financière (Sophie Laurent). "
            "Réunion de validation planifiée le 20/01."
        ),
        category="Support Général",
        subcategory="Autre Demande",
        priority="HIGH",
        status="PENDING",
        user_email="yasmine.hammami@geiser.com",
        days_ago_created=7,
        sla_status="PAUSED",
        tags=["microsoft", "ea", "contrat", "m365", "azure", "renouvellement"],
    ),

    make_ticket(
        subject="Mise en place monitoring Grafana/Prometheus pour les APIs microservices GEISER",
        description=(
            "Demande de déploiement d'une stack de monitoring Grafana + Prometheus pour les 8 "
            "microservices de la plateforme GEISER (invoice-api, ticket-api, auth-service, etc.) "
            "hébergés sur Kubernetes (namespace: geiser-prod). "
            "Métriques souhaitées : latence P99, taux d'erreur 5xx, utilisation CPU/RAM par pod, "
            "saturation des queues RabbitMQ. "
            "Dashboards Grafana : 1 par service + 1 dashboard global. "
            "Alertes : Slack + email pour toute alerte P1. "
            "En attente d'approbation du comité architecture DSI (réunion prévue 22/01)."
        ),
        category="Infrastructure & Réseau",
        subcategory="Serveurs & Cloud",
        priority="MEDIUM",
        status="PENDING",
        user_email="bilel.aouini@geiser.com",
        days_ago_created=8,
        sla_status="PAUSED",
        tags=["grafana", "prometheus", "kubernetes", "monitoring", "microservices"],
    ),

    make_ticket(
        subject="Procédure BYOD — configuration MDM Intune pour appareils personnels équipe direction",
        description=(
            "La Direction Générale souhaite mettre en place une politique BYOD (Bring Your Own Device) "
            "pour 5 membres de l'équipe de direction permettant l'accès sécurisé aux emails, "
            "Teams et SharePoint depuis leurs iPhones personnels (iOS 17). "
            "Solution retenue : Microsoft Intune MAM (Mobile Application Management) sans MDM complet "
            "pour préserver la vie privée. "
            "Configuration requise : App Protection Policies + Conditional Access. "
            "En attente : validation juridique sur les aspects RGPD (traitement données personnelles)."
        ),
        category="Authentification & Accès",
        subcategory="Double Facteur (2FA)",
        priority="MEDIUM",
        status="PENDING",
        user_email="yasmine.hammami@geiser.com",
        days_ago_created=5,
        sla_status="PAUSED",
        tags=["byod", "intune", "mdm", "ios", "rgpd", "direction"],
    ),

    # ──────────────────────── CLOSED (2) ──────────────────────────────────────

    make_ticket(
        subject="Remplacement disque SSD défaillant — HP EliteBook 840 G9 de Nicolas Petit",
        description=(
            "Mon ordinateur portable HP EliteBook 840 G9 affiche des erreurs SMART depuis 3 jours : "
            "'Warning: Drive failure expected' dans HP Sure Predict (application de diagnostic HP). "
            "Paramètre SMART inquiétant : Reallocated Sectors Count = 127 (seuil critique : 5). "
            "SSD : Samsung PM9A1 512GB NVMe. "
            "Aucune perte de données pour le moment (backup automatique OneDrive actif). "
            "Remplacement préventif recommandé avant panne totale."
        ),
        category="Matériel & Poste de Travail",
        subcategory="PC Portable / Fixe",
        priority="HIGH",
        status="CLOSED",
        user_email="nicolas.petit@geiser.com",
        days_ago_created=20,
        resolution_note=(
            "Disque SSD Samsung PM9A1 512GB remplacé par un Samsung 990 Pro 1TB NVMe sous garantie HP "
            "(contrat Care Pack 3 ans HP). Sauvegarde complète effectuée avant intervention via "
            "Macrium Reflect. Image restaurée sur le nouveau disque. "
            "Tests SMART post-remplacement : tous les paramètres dans les seuils normaux. "
            "PC restitué à Nicolas Petit avec 1TB de stockage (upgrade). Ticket fermé après validation utilisateur."
        ),
        csat_rating=5,
        csat_comment="Service excellent, mon PC est comme neuf avec le double de stockage !",
        sla_status="COMPLETED",
        tags=["ssd", "smart", "remplacement", "hp-elitebook", "garantie"],
    ),

    make_ticket(
        subject="Compte email bloqué suite à envoi massif de spams — compromission potentielle",
        description=(
            "Le compte email de Victor Morel (victor.morel@geiser.com) a été automatiquement suspendu "
            "par Exchange Online Protection (EOP) ce matin à 06h15 pour envoi massif de spams. "
            "Volume : 3 847 emails envoyés en 2h depuis son compte vers des adresses externes. "
            "Objet des spams : 'Offre exceptionnelle — gagnez 500€'. "
            "Victor confirme ne pas avoir envoyé ces emails (il dormait). "
            "Compromission de compte probable. Analyse forensique requise."
        ),
        category="Sécurité IT",
        subcategory="Incident de Sécurité (ISO 27001)",
        priority="URGENT",
        status="CLOSED",
        user_email="victor.morel@geiser.com",
        days_ago_created=25,
        resolution_note=(
            "Analyse forensique : le compte a été compromis via credential stuffing (fuite de données "
            "d'un service tiers utilisant le même mot de passe). "
            "Actions réalisées : (1) Réinitialisation immédiate du mot de passe, (2) Révocation de toutes "
            "les sessions actives (MFA de toutes les apps tierces), (3) Activation MFA obligatoire, "
            "(4) Déblocage du compte EOP après vérification (48h de quarantaine), "
            "(5) Notification aux 3 847 destinataires via postmaster@geiser.com, "
            "(6) Rapport d'incident ISO 27001 IS-2025-003. Compte réactivé le 14/01. "
            "Recommandation : déploiement Have I Been Pwned monitoring pour tous les comptes."
        ),
        csat_rating=4,
        csat_comment="Situation stressante mais gérée efficacement par l'équipe sécurité.",
        sla_status="COMPLETED",
        tags=["compromission", "spam", "exchange", "iso27001", "forensique", "eop"],
    ),
]


# ── Insert tickets (idempotent by subject) ─────────────────────────────────────
inserted_tickets = 0
skipped_tickets = 0

for t in tickets_to_add:
    existing = db.tickets.find_one({"subject": t["subject"]})
    if existing:
        skipped_tickets += 1
        print(f"  [SKIP ticket] {t['subject'][:70]}...")
    else:
        db.tickets.insert_one(t)
        inserted_tickets += 1
        status_icon = {"RESOLVED": "[OK]", "CLOSED": "[CLOSED]", "IN_PROGRESS": "[IN_PROGRESS]", "OPEN": "[OPEN]", "PENDING": "[PENDING]"}.get(t["status"], "?")
        print(f"  {status_icon} [{t['priority']:<6}] {t['subject'][:70]}")

print(f"\n[OK] Tickets: {inserted_tickets} inserted, {skipped_tickets} already existed\n")

# ── Final counts ───────────────────────────────────────────────────────────────
print("=" * 60)
print("[DB] FINAL DATABASE COUNTS")
print("=" * 60)
for col in ["users", "agents", "teams", "tickets", "notifications", "sla_alerts"]:
    count = db[col].count_documents({})
    print(f"  {col:<20}: {count}")

print("\n[STATS] TICKET STATUS BREAKDOWN")
pipeline = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
for r in db.tickets.aggregate(pipeline):
    print(f"  {r['_id']:<15}: {r['count']}")

print("\n[CSAT] CSAT STATS")
csat_pipeline = [
    {"$match": {"satisfaction_rating": {"$ne": None}}},
    {"$group": {"_id": None,
                "count": {"$sum": 1},
                "avg": {"$avg": "$satisfaction_rating"}}}
]
for r in db.tickets.aggregate(csat_pipeline):
    print(f"  Tickets évalués : {r['count']}  |  Moyenne : {r['avg']:.2f}/5")

print("\n[OK] Seeding batch 2 complete!\n")
