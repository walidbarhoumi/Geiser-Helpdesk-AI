# 🛡️ GEISER Helpdesk AI

[![pipeline status](https://gitlab.com/geiser-group1/Geiser-Helpdesk-AI/badges/main/pipeline.svg)](https://gitlab.com/geiser-group1/Geiser-Helpdesk-AI/-/commits/main)
[![Latest Release](https://gitlab.com/geiser-group1/Geiser-Helpdesk-AI/-/badges/release.svg)](https://gitlab.com/geiser-group1/Geiser-Helpdesk-AI/-/releases)
![Python](https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.151-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![Flutter](https://img.shields.io/badge/Flutter-Mobile-02569B?logo=flutter&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Atlas-47A248?logo=mongodb&logoColor=white)
![ISO 27001](https://img.shields.io/badge/Security-ISO%2027001%20Compliant-blue)

> **Plateforme Intelligente de Gestion de Tickets ITSM assistée par Intelligence Artificielle (RAG, DeepEval, Triage Automatisé & Multi-plateforme Web, Mobile et Bureau).**

---

## 🚀 Architecture Globale

- **Backend** : FastAPI, Python 3.10, Motor (Async MongoDB), LangChain, FAISS Vector Store, DeepEval Framework.
- **Frontend Web** : React 19, TypeScript, Vite, TailwindCSS, Framer Motion, Axios.
- **Mobile** : Flutter 3.x (Android & iOS), Provider, Dio.
- **Desktop** : Tauri 2.0 (Rust + Webview).
- **IA & NLP** : Ollama (Gemma 3 / Llama 3), DeepEval (Évaluation RAG Triad, Faithfulness, Relevancy), Classifieur Hybride.
- **Sécurité** : JWT Blacklist, 2FA TOTP, RBAC (Admin, Supervisor, Agent, User), Audit Logs ISO 27001, Rate Limiting.

---

## 🔄 GitLab CI/CD Pipeline

Le projet intègre une pipeline d'intégration continue complète via GitLab CI/CD (`.gitlab-ci.yml`) :

| Étape | Job | Description |
|---|---|---|
| **Lint** | `lint:backend` | Vérification de syntaxe et compilation Python (`compileall`) |
| **Lint** | `lint:frontend` | Validation stricte du typage TypeScript (`tsc --noEmit`) |
| **Test** | `test:backend-unit` | 76 tests automatisés (ITIL Matrix, SLA Granulaires, JWT Blacklist, CSAT, Sécurité Upload) |
| **Build** | `build:frontend` | Compilation du bundle de production React (Vite) avec génération d'artefacts |

---

## 🛠️ Démarrage Rapide

### 1. Cloner le projet
```bash
git clone https://gitlab.com/geiser-group1/Geiser-Helpdesk-AI.git
cd Geiser-Helpdesk-AI
```

### 2. Backend (FastAPI)
```bash
cd backend
python -m venv venv
# Activer le venv puis :
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend (React / Vite)
```bash
cd frontend
npm install
npm run dev
```

### 4. Tests Unitaires
```bash
cd backend
pytest -v
```

---

## 👥 Auteur & Projet
- **Projet** : GEISER Helpdesk AI — PFE 2026
- **Organisation** : [Geiser-group](https://gitlab.com/geiser-group1)
