# Guide de Démarrage — Application Mobile Flutter GEISER Support IA

L'application mobile Flutter a été créée avec succès dans le répertoire exact demandé :
c:\Users\bwali\Documents\geiser\mobile flutter

---

## 📱 Fonctionnalités Incluses

1. **Authentification & Session JWT**
   - Connexion (/api/v1/auth/login) et Inscription (/api/v1/auth/register).
   - Persistance sécurisée du Token Bearer via SharedPreferences.
   - Intercepteur Dio automatique pour ajouter l'en-tête Authorization: Bearer <token> sur chaque requête.

2. **Assistance IA & Moteur RAG FAISS**
   - Écran de messagerie multi-tours en temps réel avec **GEISER Bot IA** (/api/v1/chat/message).
   - Suggestions interactives cliquables (Chips) issues du dataset de connaissances.
   - Bouton de transfert / escalade automatique en Ticket IT officiel (/api/v1/chat/escalate).

3. **Gestion des Tickets IT & Incidents**
   - Visualisation de la liste des tickets de l'utilisateur (/api/v1/tickets/).
   - Formulaire de déclaration d'incident avec sélection de catégorie et priorité P1 à P4 (/api/v1/tickets/create).
   - Affichage des résolutions techniques apportées par les techniciens N2/N3.

4. **Profil Utilisateur & Paramètres**
   - Informations du compte connecté, rôle (USER, AGENT, ADMIN), statut de certification ISO 27001 et déconnexion.

---

## 🛠️ Comment lancer l'application dans Android Studio

### Étape 1 : Ouvrir le projet
1. Lancez **Android Studio**.
2. Cliquez sur **Open** (ou *File > Open*).
3. Sélectionnez le dossier : c:\Users\bwali\Documents\geiser\mobile flutter.

### Étape 2 : Installer les dépendances
Ouvrez le terminal intégré dans Android Studio ou votre PowerShell dans le dossier mobile flutter et lancez :
`ash
flutter pub get
`

### Étape 3 : Vérifier l'adresse de l'API (pi_constants.dart)
Le fichier lib/core/constants/api_constants.dart est configuré pour :
- **Émulateur Android officiel** : http://10.0.2.2:8000/api/v1 (redirige automatiquement vers localhost:8000 de votre PC).
- **Téléphone physique Android connecté en USB/Wi-Fi** : remplacez 10.0.2.2 par l'adresse IP locale de votre machine (ex: http://192.168.1.50:8000/api/v1).

### Étape 4 : Lancer le Backend FastAPI
Assurez-vous que votre serveur backend FastAPI tourne sur votre machine :
`powershell
cd c:\Users\bwali\Documents\geiser\backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
`

### Étape 5 : Lancer l'application
Dans Android Studio, sélectionnez un émulateur ou appareil Android dans la barre d'outils, puis cliquez sur le bouton vert **Run ▶** (ou tapez lutter run).
