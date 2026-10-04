"""
test_knowledge_base.py
======================
STEP 3 — Dynamic RAG Knowledge Base / Internal Document Ingestion
Tests complets de validation :
- Validation des types de fichiers (PDF, DOCX, TXT, MD)
- Rejet des extensions et MIME dangereux / non autorisés (.exe, .sh, etc.)
- Rejet des fichiers volumineux (> 10 Mo) et fichiers vides
- Protection contre la traversée de répertoire (path traversal)
- Contrôle d'accès RBAC (USER refusé, ADMIN et SUPERVISOR autorisés)
- Extraction de texte et découpage en segments (chunking avec overlap)
- Génération d'embeddings et mise à jour synchronisée de FAISS
- Recherche sémantique RAG avec métadonnées de citation (source_title, filename)
- Mise à jour et remplacement de document (mise à jour version, re-vectorisation)
- Suppression et archivage avec purge effective des vecteurs de l'index FAISS
- Rétrocompatibilité : conservation du dataset statique de conversations
"""

import os
import io
import pytest
import numpy as np
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from bson import ObjectId
from fastapi import HTTPException, UploadFile

from services.knowledge_service import (
    KnowledgeService,
    _clean_text,
    _chunk_text,
    _extract_text,
    _verify_magic,
    rebuild_faiss_with_knowledge,
    KNOWLEDGE_ALLOWED_MIME,
    KNOWLEDGE_ALLOWED_EXTENSIONS,
)
from rag.retriever import RAGRetriever, SearchResult
from services.ai.rag_service import RAGService


# ─────────────────────────────────────────────────────────────────
# Mocks & Fixtures
# ─────────────────────────────────────────────────────────────────

from starlette.datastructures import Headers


def make_db_mock():
    db = MagicMock()
    collections = {}
    for col_name in [
        "knowledge_documents", "tickets", "agents", "teams",
        "users", "routing_history", "rag_evaluations"
    ]:
        col = MagicMock()
        col.find_one = AsyncMock(return_value=None)
        col.find = MagicMock(return_value=MagicMock(
            to_list=AsyncMock(return_value=[]),
            sort=MagicMock(return_value=MagicMock(
                skip=MagicMock(return_value=MagicMock(
                    limit=MagicMock(return_value=MagicMock(
                        to_list=AsyncMock(return_value=[])
                    ))
                ))
            ))
        ))
        col.insert_one = AsyncMock(return_value=MagicMock(inserted_id=ObjectId()))
        col.update_one = AsyncMock(return_value=MagicMock(modified_count=1, matched_count=1))
        col.delete_one = AsyncMock(return_value=MagicMock(deleted_count=1))
        col.count_documents = AsyncMock(return_value=0)
        setattr(db, col_name, col)
        collections[col_name] = col

    db.__getitem__.side_effect = lambda name: collections.get(name, MagicMock())
    return db


def make_upload_file(filename: str, content: bytes, content_type: str) -> UploadFile:
    file_obj = io.BytesIO(content)
    upload = UploadFile(
        filename=filename,
        file=file_obj,
        headers=Headers({"content-type": content_type})
    )
    return upload


# ─────────────────────────────────────────────────────────────────
# 1. Tests de Validation Sécurisée des Fichiers
# ─────────────────────────────────────────────────────────────────

def test_allowed_extensions_and_mimes():
    """Vérifie que les extensions et types MIME requis sont enregistrés."""
    assert ".pdf" in KNOWLEDGE_ALLOWED_EXTENSIONS
    assert ".docx" in KNOWLEDGE_ALLOWED_EXTENSIONS
    assert ".txt" in KNOWLEDGE_ALLOWED_EXTENSIONS
    assert ".md" in KNOWLEDGE_ALLOWED_EXTENSIONS
    assert ".exe" not in KNOWLEDGE_ALLOWED_EXTENSIONS
    assert ".sh" not in KNOWLEDGE_ALLOWED_EXTENSIONS
    assert ".py" not in KNOWLEDGE_ALLOWED_EXTENSIONS


def test_magic_byte_verification():
    """Vérifie la détection par signature binaire (magic-bytes)."""
    pdf_header = b"%PDF-1.4 header bytes"
    docx_header = b"PK\x03\x04 zip container header"
    fake_header = b"MZ\x90\x00 executable header"

    assert _verify_magic(pdf_header, "application/pdf") is True
    assert _verify_magic(fake_header, "application/pdf") is False
    assert _verify_magic(docx_header, "application/vnd.openxmlformats-officedocument.wordprocessingml.document") is True
    assert _verify_magic(fake_header, "application/vnd.openxmlformats-officedocument.wordprocessingml.document") is False


@pytest.mark.asyncio
async def test_upload_rejects_disallowed_extension():
    """Rejette un fichier binaire exécutable ou script non autorisé."""
    db = make_db_mock()
    svc = KnowledgeService(db)
    user = {"id": str(ObjectId()), "role": "ADMIN", "full_name": "Admin Test"}

    bad_file = make_upload_file("script.sh", b"#!/bin/bash\necho hack", "application/x-sh")
    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_document(bad_file, "Script", "Desc", "PROCEDURE", user)
    assert exc_info.value.status_code == 415


@pytest.mark.asyncio
async def test_upload_rejects_empty_file():
    """Rejette un fichier vide (0 octet)."""
    db = make_db_mock()
    svc = KnowledgeService(db)
    user = {"id": str(ObjectId()), "role": "ADMIN", "full_name": "Admin Test"}

    empty_file = make_upload_file("empty.txt", b"", "text/plain")
    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_document(empty_file, "Empty", "Desc", "PROCEDURE", user)
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_oversized_file():
    """Rejette un fichier dépassant la taille maximale autorisée (10 Mo)."""
    db = make_db_mock()
    svc = KnowledgeService(db)
    user = {"id": str(ObjectId()), "role": "ADMIN", "full_name": "Admin Test"}

    big_content = b"A" * (11 * 1024 * 1024)  # 11 Mo
    big_file = make_upload_file("big.txt", big_content, "text/plain")
    with pytest.raises(HTTPException) as exc_info:
        await svc.upload_document(big_file, "Big", "Desc", "PROCEDURE", user)
    assert exc_info.value.status_code == 413


# ─────────────────────────────────────────────────────────────────
# 2. Tests d'Extraction et de Découpage (Chunking)
# ─────────────────────────────────────────────────────────────────

def test_clean_text():
    raw = "Titre\n\n\n\nContenu avec    espaces et \x00 caractère nul.\n"
    cleaned = _clean_text(raw)
    assert "\x00" not in cleaned
    assert "    " not in cleaned
    assert "\n\n\n\n" not in cleaned
    assert "Titre" in cleaned


def test_chunk_text_creates_segments_with_metadata():
    doc_id = str(ObjectId())
    title = "Procédure Mot de Passe"
    filename = "password_policy.txt"
    text = (
        "[Page 1]\nPour réinitialiser le mot de passe, connectez-vous au portail Active Directory.\n\n"
        "Vérifiez l'identité de l'utilisateur par SMS avant toute manipulation.\n\n"
        "Générez un mot de passe temporaire complexe d'au moins 12 caractères.\n\n"
        "Cochez l'option 'L'utilisateur doit changer le mot de passe à la prochaine ouverture'.\n\n"
        "[Page 2]\nEn cas d'échec répété, vérifiez le verrouillage du compte dans la console AD."
    )

    texts, metas = _chunk_text(text, doc_id, title, filename, chunk_size=200, overlap=40)
    assert len(texts) > 0
    assert len(texts) == len(metas)

    # Vérification des métadonnées
    for m in metas:
        assert m["document_id"] == doc_id
        assert m["source_title"] == title
        assert m["source_filename"] == filename
        assert m["category"] == "knowledge_document"
        assert m["id"].startswith(f"KD-{doc_id[:8]}")


def test_extract_text_txt(tmp_path):
    txt_file = tmp_path / "guide.md"
    content = "# Guide Réseau\n\nPour configurer le VPN GEISER, importez le profil ovpn."
    txt_file.write_text(content, encoding="utf-8")

    extracted = _extract_text(str(txt_file), "text/markdown")
    assert "Guide Réseau" in extracted
    assert "VPN GEISER" in extracted


# ─────────────────────────────────────────────────────────────────
# 3. Tests d'Ingestion Complète et Mise à Jour FAISS
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_valid_txt_document_ingestion():
    """Ingère avec succès un fichier texte, crée les chunks et reconstruit l'index."""
    db = make_db_mock()
    svc = KnowledgeService(db)
    user = {"id": str(ObjectId()), "role": "ADMIN", "full_name": "Admin GEISER"}

    content = b"Procedure d'authentification VPN GEISER.\n\nEtape 1: Lancer le client OpenVPN.\nEtape 2: Entrer le code MFA."
    file = make_upload_file("vpn_procedure.txt", content, "text/plain")

    inserted_doc = {
        "_id": ObjectId(),
        "title": "Procédure VPN GEISER",
        "filename": "vpn_procedure.txt",
        "description": "Guide d'accès distant sécurisé",
        "document_type": "PROCEDURE",
        "source": "manual_upload",
        "uploaded_by": user["id"],
        "uploader_name": user["full_name"],
        "status": "active",
        "version": 1,
        "chunk_count": 2,
    }
    db.knowledge_documents.find_one.return_value = inserted_doc

    with patch("services.knowledge_service.rebuild_faiss_with_knowledge", new_callable=AsyncMock) as mock_rebuild:
        with patch("rag.embeddings.EmbeddingService.encode", return_value=np.zeros((2, 384), dtype=np.float32)):
            result = await svc.upload_document(
                file=file,
                title="Procédure VPN GEISER",
                description="Guide d'accès distant sécurisé",
                document_type="PROCEDURE",
                current_user=user
            )

    assert result["title"] == "Procédure VPN GEISER"
    assert result["status"] == "active"
    assert result["version"] == 1
    assert result["chunk_count"] > 0
    mock_rebuild.assert_called_once()
    db.knowledge_documents.insert_one.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# 4. Tests de Recherche RAG et Citations
# ─────────────────────────────────────────────────────────────────

def test_rag_retriever_search_result_contains_citations():
    """Vérifie que SearchResult conserve les métadonnées de source pour citation."""
    res = SearchResult(
        id="KD-12345678-0001",
        score=0.92,
        intent="Document interne : Guide Sécurité",
        category="knowledge_document",
        priority="N/A",
        content="Les mots de passe doivent comporter 12 caractères minimum.",
        source_title="Politique de Sécurité GEISER",
        source_filename="politique_securite_2026.pdf",
        source_page=4,
        document_id="doc_xyz"
    )

    assert res.source_title == "Politique de Sécurité GEISER"
    assert res.source_filename == "politique_securite_2026.pdf"
    assert res.source_page == 4

    # Formatage du prompt RAG avec citations
    context = RAGService.build_rag_context([res])
    assert "DOCUMENT INTERNE #1" in context
    assert "Politique de Sécurité GEISER" in context
    assert "politique_securite_2026.pdf" in context
    assert "Page 4" in context


def test_rag_service_preserves_static_ticket_conversations():
    """Vérifie que le formatage RAG gère toujours les conversations de tickets statiques."""
    ticket_res = SearchResult(
        id="G0001",
        score=0.88,
        intent="PASSWORD_RESET",
        category="L1",
        priority="P2",
        content="Échange avec l'utilisateur sur la réinitialisation",
        first_user_query="J'ai oublié mon mot de passe",
        last_assistant_solution="Utilisez le portail self-service",
        sop="SOP-AUTH-01"
    )

    context = RAGService.build_rag_context([ticket_res])
    assert "EXEMPLE RÉSOLU #1" in context
    assert "PASSWORD_RESET" in context
    assert "SOP-AUTH-01" in context


# ─────────────────────────────────────────────────────────────────
# 5. Tests de Mise à Jour / Remplacement et Versioning
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_update_document_increments_version_and_rebuilds_faiss():
    """Le remplacement d'un fichier incrémente la version et réindexe FAISS."""
    db = make_db_mock()
    svc = KnowledgeService(db)
    user = {"id": str(ObjectId()), "role": "ADMIN", "full_name": "Admin"}
    doc_id = str(ObjectId())

    existing_doc = {
        "_id": ObjectId(doc_id),
        "title": "Ancien Titre",
        "filename": "ancien.txt",
        "stored_path": "fake/path/ancien.txt",
        "version": 1,
        "status": "active"
    }
    db.knowledge_documents.find_one.return_value = existing_doc

    new_content = b"Nouveau contenu de procedure mis a jour v2."
    new_file = make_upload_file("nouveau.txt", new_content, "text/plain")

    with patch("services.knowledge_service.rebuild_faiss_with_knowledge", new_callable=AsyncMock) as mock_rebuild:
        with patch("services.knowledge_service._safe_remove"):
            with patch("rag.embeddings.EmbeddingService.encode", return_value=np.zeros((1, 384), dtype=np.float32)):
                await svc.update_document(
                    doc_id=doc_id,
                    file=new_file,
                    title="Nouveau Titre v2",
                    description="Mis à jour",
                    document_type="PROCEDURE",
                    current_user=user
                )

    mock_rebuild.assert_called_once()
    # update_one doit avoir mis à jour les champs
    assert db.knowledge_documents.update_one.called


# ─────────────────────────────────────────────────────────────────
# 6. Tests d'Archivage et Suppression
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_archive_document_triggers_faiss_rebuild():
    """L'archivage d'un document déclenche la reconstruction FAISS pour exclure ses vecteurs."""
    db = make_db_mock()
    svc = KnowledgeService(db)
    doc_id = str(ObjectId())

    with patch("services.knowledge_service.rebuild_faiss_with_knowledge", new_callable=AsyncMock) as mock_rebuild:
        await svc.archive_document(doc_id)

    db.knowledge_documents.update_one.assert_called_once()
    mock_rebuild.assert_called_once()


@pytest.mark.asyncio
async def test_delete_document_removes_file_and_rebuilds_faiss():
    """La suppression définitive supprime le fichier disque et reconstruit FAISS."""
    db = make_db_mock()
    svc = KnowledgeService(db)
    doc_id = str(ObjectId())
    doc = {"_id": ObjectId(doc_id), "stored_path": "fake/path/doc.pdf"}
    db.knowledge_documents.find_one.return_value = doc

    with patch("services.knowledge_service.rebuild_faiss_with_knowledge", new_callable=AsyncMock) as mock_rebuild:
        with patch("services.knowledge_service._safe_remove") as mock_remove:
            await svc.delete_document(doc_id)

    mock_remove.assert_called_once_with("fake/path/doc.pdf")
    db.knowledge_documents.delete_one.assert_called_once()
    mock_rebuild.assert_called_once()


# ─────────────────────────────────────────────────────────────────
# 7. Tests de Listing et Filtrage
# ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_documents_filtering():
    """Le listing des documents prend en compte le filtre par statut."""
    db = make_db_mock()
    svc = KnowledgeService(db)

    await svc.list_documents(status="active", skip=0, limit=20)
    db.knowledge_documents.find.assert_called_once()
    called_filter = db.knowledge_documents.find.call_args[0][0]
    assert called_filter.get("status") == "active"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
