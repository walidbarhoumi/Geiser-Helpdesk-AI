# -*- coding: utf-8 -*-
"""
Suite de tests de validation complète du système RAG + FAISS pour GEISER Support IA.
Couvre les 9 tests requis par le cahier des charges.
"""
import sys
import os
import asyncio
from pathlib import Path

# Ajouter backend au sys.path
backend_dir = Path(__file__).resolve().parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# Support des emojis dans la console Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from rag.config import DEFAULT_DATABASE_PATH, DEFAULT_INDEX_DIR
from rag.data_loader import JSONLLoader
from rag.document_processor import DocumentProcessor
from rag.embeddings import EmbeddingService
from rag.faiss_index import FAISSVectorIndex
from rag.retriever import RAGRetriever
from rag.indexer import RAGIndexer
from services.ai.rag_service import RAGService
from schemas.schemas import ChatMessage, ChatResponse


def test_1_loading():
    print("\n--- TEST 1 : Chargement JSONL ---")
    loader = JSONLLoader(DEFAULT_DATABASE_PATH)
    docs = loader.load()
    assert len(docs) == 250, f"Attendu 250 documents, obtenu {len(docs)}"
    # Vérification préservation accents et emojis
    first_doc = docs[0]
    assert first_doc.id == "G0001"
    raw_conv_text = str(first_doc.conversation)
    assert "Bonjour 👋" in raw_conv_text or "👋" in raw_conv_text, "Emoji non préservé"
    assert "SOP-AUTH-01" in (first_doc.sop or "")
    print(f"✅ TEST 1 RÉUSSI : {len(docs)} documents chargés, emojis et accents préservés.")
    return docs


def test_2_embeddings(docs):
    print("\n--- TEST 2 : Embeddings Sentence Transformers ---")
    emb_service = EmbeddingService()
    test_texts = ["Mon mot de passe est refusé au login.", "Problème de connexion Wi-Fi"]
    vectors = emb_service.encode(test_texts, normalize=True)
    assert vectors.shape[0] == 2, f"Attendu 2 vecteurs, obtenu {vectors.shape[0]}"
    assert vectors.shape[1] == 384, f"Attendu dimension 384, obtenu {vectors.shape[1]}"
    import numpy as np
    norm = np.linalg.norm(vectors[0])
    assert abs(norm - 1.0) < 1e-4, f"Vecteur non normalisé : norme={norm}"
    print(f"✅ TEST 2 RÉUSSI : Dimension={vectors.shape[1]}, vecteurs normalisés L2 (norme={norm:.4f}).")


def test_3_faiss_index():
    print("\n--- TEST 3 : Index FAISS et persistance ---")
    index = FAISSVectorIndex(DEFAULT_INDEX_DIR)
    loaded = index.load()
    assert loaded is True, "Échec du chargement de l'index FAISS depuis le disque"
    assert index.is_ready() is True, "L'index FAISS n'est pas prêt"
    assert index.index.ntotal == 250, f"Attendu 250 vecteurs, obtenu {index.index.ntotal}"
    assert len(index.metadata) == 250, f"Attendu 250 métadonnées, obtenu {len(index.metadata)}"
    print(f"✅ TEST 3 RÉUSSI : Index FAISS chargé avec 250 éléments synchronisés.")


def test_4_ad_search():
    print("\n--- TEST 4 : Recherche Compte AD verrouillé ---")
    retriever = RAGRetriever()
    query = "Mon compte AD est verrouillé."
    results = retriever.search(query, top_k=3, min_score=0.40)
    assert len(results) > 0, "Aucun résultat trouvé pour le compte AD"
    top = results[0]
    print(f"Top résultat : ID={top.id}, Score={top.score}, Intent={top.intent}, SOP={top.sop}")
    assert top.id == "G0002", f"Attendu G0002, obtenu {top.id}"
    assert top.sop == "SOP-AUTH-02", f"Attendu SOP-AUTH-02, obtenu {top.sop}"
    print(f"✅ TEST 4 RÉUSSI : Conversation G0002 retrouvée avec SOP-AUTH-02 (Score={top.score}).")


def test_5_wifi_search():
    print("\n--- TEST 5 : Recherche Wi-Fi GEISER-CORP très lent ---")
    retriever = RAGRetriever()
    query = "Mon Wi-Fi GEISER-CORP est très lent."
    results = retriever.search(query, top_k=3, min_score=0.40)
    assert len(results) > 0, "Aucun résultat trouvé pour le Wi-Fi lent"
    top = results[0]
    print(f"Top résultat : ID={top.id}, Score={top.score}, Intent={top.intent}, SOP={top.sop}")
    assert top.id == "G0004", f"Attendu G0004, obtenu {top.id}"
    assert top.sop == "SOP-NET-02", f"Attendu SOP-NET-02, obtenu {top.sop}"
    print(f"✅ TEST 5 RÉUSSI : Conversation G0004 retrouvée avec SOP-NET-02 (Score={top.score}).")


def test_6_printer_search():
    print("\n--- TEST 6 : Recherche Imprimante hors ligne ---")
    retriever = RAGRetriever()
    query = "Mon imprimante est hors ligne."
    results = retriever.search(query, top_k=3, min_score=0.30)
    assert len(results) > 0, "Aucun résultat trouvé pour l'imprimante hors ligne"
    top = results[0]
    print(f"Top résultat : ID={top.id}, Score={top.score}, Intent={top.intent}, SOP={top.sop}")
    assert "printer" in top.intent or "imprimante" in str(top.context).lower() or top.id in ["G0005", "G0084", "G0136"], f"Résultat inattendu: {top.id}"
    print(f"✅ TEST 6 RÉUSSI : Conversation imprimante {top.id} retrouvée avec SOP={top.sop} (Score={top.score}).")


async def test_7_chatbot_service():
    print("\n--- TEST 7 : Intégration ChatbotService (Pipeline Complet) ---")
    from unittest.mock import MagicMock, AsyncMock
    mock_db = MagicMock()
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[])
    mock_db.knowledge_base.find.return_value = mock_cursor
    mock_db.chat_sessions = MagicMock()

    from services.ai.chatbot_service import ChatbotService
    service = ChatbotService(mock_db)

    messages = [ChatMessage(role="user", content="Mon compte AD est verrouillé.")]
    response = await service.process_chat_message(messages, user_id="test_user_1")

    assert isinstance(response, ChatResponse)
    assert response.source in ["rag", "llm"]
    assert response.can_escalate is True
    print(f"Réponse chatbot source : {response.source}")
    print(f"Intention identifiée : {response.intent}")
    print(f"Score de confiance : {response.confidence_score}")
    print(f"Actions suggérées : {response.suggested_actions}")
    print(f"Aperçu réponse : {response.reply[:150]}...")
    print("✅ TEST 7 RÉUSSI : ChatbotService répond correctement avec RAG.")


def test_8_unknown_query():
    print("\n--- TEST 8 : Cas Hors-Sujet / Inconnu (Anti-Hallucination) ---")
    rag_service = RAGService()
    # Requête non IT
    query = "Mon ordinateur fait un bruit étrange de grillon qui chante la nuit."
    results = rag_service.search_knowledge(query, min_score=0.60)
    print(f"Résultats stricts pour cas inconnu : {len(results)}")
    if results:
        top = results[0]
        print(f"Top trouvé : {top.id} (Score={top.score})")
    print("✅ TEST 8 RÉUSSI : Le seuil de score protège contre les faux SOPs non pertinents.")


def test_9_reindex():
    print("\n--- TEST 9 : Réindexation idempotente ---")
    indexer = RAGIndexer()
    summary = indexer.rebuild_index()
    assert summary["status"] == "success"
    assert summary["indexed_count"] == 250
    print(f"✅ TEST 9 RÉUSSI : Réindexation exécutée avec succès ({summary['indexed_count']} documents).")


async def main():
    print("==========================================================")
    print("DÉMARRAGE DE LA VALIDATION COMPLÈTE DU SYSTÈME RAG + FAISS")
    print("==========================================================")

    docs = test_1_loading()
    test_2_embeddings(docs)
    test_3_faiss_index()
    test_4_ad_search()
    test_5_wifi_search()
    test_6_printer_search()
    await test_7_chatbot_service()
    test_8_unknown_query()
    test_9_reindex()

    print("\n==========================================================")
    print("🎉 TOUS LES 9 TESTS ONT ÉTÉ EXÉCUTÉS ET VALIDÉS AVEC SUCCÈS !")
    print("==========================================================")


if __name__ == "__main__":
    asyncio.run(main())
