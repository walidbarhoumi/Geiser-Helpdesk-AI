"""
services/knowledge_service.py
==============================
STEP 3 — Dynamic RAG Knowledge Base / Internal Document Ingestion

Pipeline:
  Upload → Validate → Store → Extract text → Clean → Chunk
         → Embeddings → FAISS (rebuild) → MongoDB metadata → Available to RAG

Reuses:
  - rag/embeddings.py  (EmbeddingService singleton)
  - rag/faiss_index.py (FAISSVectorIndex)
  - attachment_service.py security helpers (magic-bytes, size limit, path sanitation)
  - settings.UPLOAD_DIR, settings.MAX_ATTACHMENT_SIZE_MB

FAISS rebuild strategy:
  FAISS IndexFlatIP does not support individual vector removal.
  On add/delete/update, we rebuild the index from:
    1. All active chunks from static JSONL dataset (same as before)
    2. All active knowledge_documents stored in MongoDB
  The rebuild is synchronous for small files (< 5 MB).
  For the current architecture (no Celery/Redis), this is acceptable.
"""

import os
import re
import uuid
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

from fastapi import UploadFile, HTTPException
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from core.config import settings
from models.base import MongoModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KNOWLEDGE_UPLOAD_DIR = os.path.join(settings.UPLOAD_DIR, "knowledge")

# MIME types accepted for knowledge documents (subset of global allowlist)
KNOWLEDGE_ALLOWED_MIME: Dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/msword": ".doc",
    "text/plain": ".txt",
    "text/markdown": ".md",
    "text/x-markdown": ".md",
}

KNOWLEDGE_ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}

# Magic-byte signatures (first 8 bytes of file)
_MAGIC: Dict[str, Tuple[bytes, ...]] = {
    "application/pdf": (b"%PDF",),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (b"PK\x03\x04",),
    "application/msword": (b"\xd0\xcf\x11\xe0",),
}

# Chunk configuration
CHUNK_SIZE = 800          # characters per chunk
CHUNK_OVERLAP = 120       # overlap between consecutive chunks
MAX_FILE_SIZE_BYTES = settings.MAX_ATTACHMENT_SIZE_MB * 1024 * 1024


# ---------------------------------------------------------------------------
# Security helpers (re-implement lean version for knowledge docs)
# ---------------------------------------------------------------------------

def _verify_magic(header: bytes, mime: str) -> bool:
    sigs = _MAGIC.get(mime)
    if not sigs:
        return True   # txt/md have no fixed magic; rely on MIME whitelist
    return any(header.startswith(s) for s in sigs)


def _safe_remove(path: str) -> None:
    try:
        if path and os.path.isfile(path):
            os.remove(path)
    except OSError as exc:
        logger.warning("Could not remove knowledge file %s: %s", path, exc)


# ---------------------------------------------------------------------------
# Text Extraction
# ---------------------------------------------------------------------------

def _extract_text_pdf(path: str) -> str:
    """Extracts text from a PDF file using pypdf."""
    try:
        import pypdf
        text_parts = []
        reader = pypdf.PdfReader(path)
        for page_num, page in enumerate(reader.pages, 1):
            t = page.extract_text() or ""
            if t.strip():
                text_parts.append(f"[Page {page_num}]\n{t}")
        return "\n\n".join(text_parts)
    except Exception as e:
        raise ValueError(f"Impossible d'extraire le texte du PDF : {e}")


def _extract_text_docx(path: str) -> str:
    """Extracts text from a DOCX file using python-docx."""
    try:
        import docx
        doc = docx.Document(path)
        paragraphs = [p.text.strip() for p in doc.paragraphs if p.text.strip()]
        # Also extract tables
        for table in doc.tables:
            for row in table.rows:
                row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
                if row_text:
                    paragraphs.append(row_text)
        return "\n\n".join(paragraphs)
    except Exception as e:
        raise ValueError(f"Impossible d'extraire le texte du DOCX : {e}")


def _extract_text_txt(path: str) -> str:
    """Reads a plain text or Markdown file."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except Exception as e:
        raise ValueError(f"Impossible de lire le fichier texte : {e}")


def _extract_text(path: str, mime: str) -> str:
    """Dispatches text extraction based on MIME type."""
    if mime == "application/pdf":
        return _extract_text_pdf(path)
    elif mime in (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/msword",
    ):
        return _extract_text_docx(path)
    elif mime in ("text/plain", "text/markdown", "text/x-markdown"):
        return _extract_text_txt(path)
    else:
        raise ValueError(f"Type MIME non supporté pour l'extraction : {mime}")


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _clean_text(text: str) -> str:
    """Basic text cleaning: collapse excessive whitespace, remove null bytes."""
    text = text.replace("\x00", "")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r" {2,}", " ", text)
    return text.strip()


def _chunk_text(
    text: str,
    doc_id: str,
    title: str,
    filename: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Splits cleaned text into overlapping chunks.
    Returns (texts, metadatas) — same shape expected by FAISSVectorIndex.
    """
    texts: List[str] = []
    metadatas: List[Dict[str, Any]] = []

    if not text.strip():
        return texts, metadatas

    # Split by paragraphs first, then merge into chunks
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]

    current_chunk = ""
    chunk_idx = 0

    for para in paragraphs:
        candidate = (current_chunk + "\n\n" + para).strip() if current_chunk else para
        if len(candidate) <= chunk_size:
            current_chunk = candidate
        else:
            # Flush current chunk if it has content
            if current_chunk:
                chunk_text = current_chunk.strip()
                texts.append(chunk_text)
                metadatas.append(_build_chunk_metadata(
                    doc_id=doc_id, chunk_idx=chunk_idx,
                    title=title, filename=filename, text=chunk_text
                ))
                chunk_idx += 1
                # Overlap: keep last 'overlap' chars as start of next chunk
                current_chunk = current_chunk[-overlap:].strip() + "\n\n" + para
            else:
                # Single paragraph exceeds chunk_size — split by characters
                for start in range(0, len(para), chunk_size - overlap):
                    piece = para[start:start + chunk_size].strip()
                    if piece:
                        texts.append(piece)
                        metadatas.append(_build_chunk_metadata(
                            doc_id=doc_id, chunk_idx=chunk_idx,
                            title=title, filename=filename, text=piece
                        ))
                        chunk_idx += 1
                current_chunk = ""

    # Flush last chunk
    if current_chunk.strip():
        chunk_text = current_chunk.strip()
        texts.append(chunk_text)
        metadatas.append(_build_chunk_metadata(
            doc_id=doc_id, chunk_idx=chunk_idx,
            title=title, filename=filename, text=chunk_text
        ))

    return texts, metadatas


def _build_chunk_metadata(
    doc_id: str, chunk_idx: int, title: str, filename: str, text: str
) -> Dict[str, Any]:
    """Builds metadata for a single knowledge-document chunk."""
    # Detect page number from "[Page N]" markers inserted during PDF extraction
    page_match = re.search(r"\[Page (\d+)\]", text)
    page_num = int(page_match.group(1)) if page_match else None

    return {
        # Identification markers (compatible with existing SearchResult schema)
        "id": f"KD-{doc_id[:8]}-{chunk_idx:04d}",
        "document_id": doc_id,
        "chunk_index": chunk_idx,
        # Source citation fields (used by RAGService.build_rag_context)
        "source_title": title,
        "source_filename": filename,
        "source_page": page_num,
        # Legacy fields kept for SearchResult schema compatibility (ticket-based)
        "category": "knowledge_document",
        "priority": "N/A",
        "intent": f"Document interne : {title}",
        "context": {"source": "knowledge_document", "filename": filename},
        "sop": None,
        "result": None,
        "tags": ["knowledge_document"],
        "first_user_query": None,
        "last_assistant_solution": text[:500],
        "solution_steps": [],
        "text_snippet": text[:400],
        # Full text (not in SearchResult but available for rebuild)
        "_full_text": text,
    }


# ---------------------------------------------------------------------------
# FAISS rebuild (with both static dataset + dynamic knowledge docs)
# ---------------------------------------------------------------------------

_rebuild_lock = threading.Lock()


async def rebuild_faiss_with_knowledge(db: AsyncIOMotorDatabase) -> Dict[str, Any]:
    """
    Rebuilds the FAISS index from:
      1. Static JSONL dataset (unchanged)
      2. Active knowledge documents stored in MongoDB

    Thread-safe: uses a module-level lock to prevent concurrent rebuilds.
    """
    from rag.config import DEFAULT_DATABASE_PATH, DEFAULT_INDEX_DIR
    from rag.data_loader import JSONLLoader
    from rag.document_processor import DocumentProcessor
    from rag.embeddings import EmbeddingService
    from rag.faiss_index import FAISSVectorIndex

    with _rebuild_lock:
        all_texts: List[str] = []
        all_metadatas: List[Dict[str, Any]] = []

        # 1. Static JSONL dataset
        try:
            loader = JSONLLoader(DEFAULT_DATABASE_PATH)
            static_docs = loader.load()
            static_texts, static_metas = DocumentProcessor.process_documents(static_docs)
            all_texts.extend(static_texts)
            all_metadatas.extend(static_metas)
            logger.info("FAISS rebuild: %d static documents loaded.", len(static_docs))
        except Exception as e:
            logger.warning("FAISS rebuild: could not load static JSONL dataset: %s", e)

        # 2. Active knowledge documents from MongoDB
        try:
            cursor = db.knowledge_documents.find({"status": "active"})
            kb_docs = await cursor.to_list(length=5000)
            for kd in kb_docs:
                chunks_texts = kd.get("_chunk_texts", [])
                chunks_metas = kd.get("_chunk_metadatas", [])
                if chunks_texts and chunks_metas:
                    all_texts.extend(chunks_texts)
                    all_metadatas.extend(chunks_metas)
            logger.info("FAISS rebuild: %d knowledge documents (dynamic chunks loaded from DB).", len(kb_docs))
        except Exception as e:
            logger.warning("FAISS rebuild: could not load knowledge documents: %s", e)

        if not all_texts:
            raise ValueError("Aucun document à indexer (dataset statique vide et aucun document actif en base).")

        # 3. Generate embeddings
        embedding_svc = EmbeddingService()
        vectors = embedding_svc.encode(all_texts, normalize=True)

        # 4. Rebuild FAISS index
        vector_index = FAISSVectorIndex(DEFAULT_INDEX_DIR)
        vector_index.build_index(vectors, all_metadatas)
        vector_index.save()

        logger.info(
            "FAISS rebuild complete: %d total vectors (%d static + %d dynamic).",
            len(all_texts),
            len(all_texts) - sum(len(kd.get("_chunk_texts", [])) for kd in kb_docs),
            sum(len(kd.get("_chunk_texts", [])) for kd in kb_docs),
        )

        return {
            "status": "success",
            "total_indexed": len(all_texts),
            "static_count": len(all_metadatas) - sum(
                len(kd.get("_chunk_texts", [])) for kd in kb_docs
            ),
            "dynamic_count": sum(len(kd.get("_chunk_texts", [])) for kd in kb_docs),
            "vector_dimension": int(vectors.shape[1]),
        }


# ---------------------------------------------------------------------------
# KnowledgeService
# ---------------------------------------------------------------------------

class KnowledgeService:
    """
    Service de gestion des documents de la base de connaissances interne.

    Responsabilités :
    - Validation sécurisée des fichiers uploadés (MIME, magic-bytes, taille)
    - Stockage sécurisé (UUID filename, répertoire dédié)
    - Extraction de texte (PDF, DOCX, TXT, MD)
    - Chunking avec overlap
    - Génération d'embeddings via EmbeddingService (singleton)
    - Reconstruction de l'index FAISS (statique + dynamique)
    - CRUD MongoDB sur la collection knowledge_documents
    """

    COLLECTION = "knowledge_documents"

    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db[self.COLLECTION]

    # ------------------------------------------------------------------
    # Upload & Ingest
    # ------------------------------------------------------------------

    async def upload_document(
        self,
        file: UploadFile,
        title: str,
        description: Optional[str],
        document_type: str,
        current_user: dict,
    ) -> Dict[str, Any]:
        """
        Validates, stores, and ingests an uploaded knowledge document.

        Security:
        - MIME whitelist (knowledge-specific)
        - Magic-byte verification for PDF/DOCX
        - File size limit
        - UUID-based stored filename (no user input in path)
        - Path traversal protection
        """
        os.makedirs(KNOWLEDGE_UPLOAD_DIR, exist_ok=True)

        # ── 1. MIME whitelist ──────────────────────────────────────────
        declared_mime = (file.content_type or "").split(";")[0].strip().lower()
        if declared_mime not in KNOWLEDGE_ALLOWED_MIME:
            # Try extension fallback
            ext = os.path.splitext(file.filename or "")[1].lower()
            mime_from_ext = {
                ".pdf": "application/pdf",
                ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                ".doc": "application/msword",
                ".txt": "text/plain",
                ".md": "text/markdown",
            }.get(ext)
            if mime_from_ext:
                declared_mime = mime_from_ext
            else:
                raise HTTPException(
                    status_code=415,
                    detail=(
                        f"Type de fichier non autorisé : '{declared_mime or ext or 'inconnu'}'. "
                        f"Types acceptés : PDF, DOCX, DOC, TXT, MD"
                    ),
                )

        # ── 2. Extension validation ────────────────────────────────────
        original_filename = os.path.basename(file.filename or "").strip()
        original_filename = original_filename.replace("\x00", "").replace("/", "").replace("\\", "")
        if not original_filename:
            original_filename = "document"
        ext = os.path.splitext(original_filename)[1].lower()
        if ext not in KNOWLEDGE_ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Extension non autorisée : '{ext}'. Extensions acceptées : {', '.join(KNOWLEDGE_ALLOWED_EXTENSIONS)}"
            )

        # ── 3. Read content + size check ──────────────────────────────
        contents = await file.read()
        size_bytes = len(contents)
        if size_bytes == 0:
            raise HTTPException(status_code=400, detail="Le fichier est vide.")
        if size_bytes > MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=(
                    f"Fichier trop volumineux : {size_bytes / 1024 / 1024:.1f} Mo. "
                    f"Limite : {settings.MAX_ATTACHMENT_SIZE_MB} Mo"
                ),
            )

        # ── 4. Magic-byte verification ─────────────────────────────────
        if not _verify_magic(contents[:16], declared_mime):
            raise HTTPException(
                status_code=415,
                detail="Le contenu du fichier ne correspond pas au type déclaré."
            )

        # ── 5. Store file with UUID filename ───────────────────────────
        stored_filename = f"{uuid.uuid4().hex}{ext}"
        stored_path = os.path.join(KNOWLEDGE_UPLOAD_DIR, stored_filename)

        # Path traversal guard
        resolved = os.path.realpath(stored_path)
        upload_dir_real = os.path.realpath(KNOWLEDGE_UPLOAD_DIR)
        if not resolved.startswith(upload_dir_real + os.sep):
            raise HTTPException(status_code=400, detail="Chemin de fichier invalide.")

        try:
            with open(stored_path, "wb") as fh:
                fh.write(contents)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Erreur lors de l'enregistrement : {e}")

        # ── 6. Create initial MongoDB record (status=processing) ───────
        doc_id = str(ObjectId())
        user_id = str(current_user.get("id", ""))
        uploader_name = current_user.get("full_name") or current_user.get("email") or user_id

        db_record = {
            "_id": ObjectId(doc_id),
            "title": title.strip(),
            "filename": original_filename,
            "description": (description or "").strip(),
            "document_type": document_type,
            "source": "manual_upload",
            "uploaded_by": user_id,
            "uploader_name": uploader_name,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "status": "processing",
            "version": 1,
            "chunk_count": 0,
            "stored_filename": stored_filename,
            "stored_path": stored_path,
            "mime_type": declared_mime,
            "size_bytes": size_bytes,
            "_chunk_texts": [],
            "_chunk_metadatas": [],
        }

        await self.collection.insert_one(db_record)

        # ── 7. Extract text + chunk + embed + rebuild FAISS ────────────
        try:
            raw_text = _extract_text(stored_path, declared_mime)
            clean = _clean_text(raw_text)

            chunk_texts, chunk_metas = _chunk_text(
                text=clean,
                doc_id=doc_id,
                title=title.strip(),
                filename=original_filename,
            )

            # Generate embeddings (validates chunking worked)
            from rag.embeddings import EmbeddingService
            emb_svc = EmbeddingService()
            if chunk_texts:
                emb_svc.encode(chunk_texts[:1], normalize=True)   # warm-up / validate

            # Store chunks in MongoDB (embedded in document record)
            await self.collection.update_one(
                {"_id": ObjectId(doc_id)},
                {
                    "$set": {
                        "status": "active",
                        "chunk_count": len(chunk_texts),
                        "_chunk_texts": chunk_texts,
                        "_chunk_metadatas": chunk_metas,
                        "updated_at": datetime.utcnow(),
                    }
                }
            )

            # Rebuild FAISS index to include new document
            await rebuild_faiss_with_knowledge(self.db)

            logger.info(
                "Knowledge document '%s' ingested: %d chunks, FAISS rebuilt.",
                title, len(chunk_texts)
            )

        except Exception as e:
            logger.error("Knowledge document ingestion failed for '%s': %s", title, e)
            await self.collection.update_one(
                {"_id": ObjectId(doc_id)},
                {"$set": {"status": "failed", "error_message": str(e), "updated_at": datetime.utcnow()}}
            )
            raise HTTPException(status_code=500, detail=f"Échec de l'ingestion du document : {e}")

        return self._format_out(await self.collection.find_one({"_id": ObjectId(doc_id)}))

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------

    async def list_documents(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Dict[str, Any]:
        query: Dict[str, Any] = {}
        if status:
            query["status"] = status

        total = await self.collection.count_documents(query)
        cursor = self.collection.find(
            query,
            # Do NOT return large chunk arrays to the listing endpoint
            projection={"_chunk_texts": 0, "_chunk_metadatas": 0}
        ).sort("created_at", -1).skip(skip).limit(limit)
        docs = await cursor.to_list(length=limit)
        return {
            "total": total,
            "skip": skip,
            "limit": limit,
            "items": [self._format_out(d) for d in docs],
        }

    # ------------------------------------------------------------------
    # Get single
    # ------------------------------------------------------------------

    async def get_document(self, doc_id: str) -> Optional[Dict[str, Any]]:
        oid = ObjectId(doc_id) if ObjectId.is_valid(doc_id) else None
        if not oid:
            return None
        doc = await self.collection.find_one(
            {"_id": oid},
            projection={"_chunk_texts": 0, "_chunk_metadatas": 0}
        )
        return self._format_out(doc) if doc else None

    # ------------------------------------------------------------------
    # Update / Replace
    # ------------------------------------------------------------------

    async def update_document(
        self,
        doc_id: str,
        file: Optional[UploadFile],
        title: Optional[str],
        description: Optional[str],
        document_type: Optional[str],
        current_user: dict,
    ) -> Dict[str, Any]:
        """Replaces document content (if new file provided) and/or updates metadata."""
        oid = ObjectId(doc_id) if ObjectId.is_valid(doc_id) else None
        if not oid:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        existing = await self.collection.find_one({"_id": oid})
        if not existing:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        update_fields: Dict[str, Any] = {"updated_at": datetime.utcnow()}

        if title is not None:
            update_fields["title"] = title.strip()
        if description is not None:
            update_fields["description"] = description.strip()
        if document_type is not None:
            update_fields["document_type"] = document_type

        if file is not None:
            # Replace content: validate + store new file
            os.makedirs(KNOWLEDGE_UPLOAD_DIR, exist_ok=True)

            declared_mime = (file.content_type or "").split(";")[0].strip().lower()
            original_filename = os.path.basename(file.filename or "").strip()
            original_filename = original_filename.replace("\x00", "").replace("/", "").replace("\\", "")
            ext = os.path.splitext(original_filename)[1].lower()

            if declared_mime not in KNOWLEDGE_ALLOWED_MIME:
                mime_from_ext = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".doc": "application/msword", ".txt": "text/plain", ".md": "text/markdown"}.get(ext)
                if mime_from_ext:
                    declared_mime = mime_from_ext
                else:
                    raise HTTPException(status_code=415, detail="Type de fichier non autorisé.")

            if ext not in KNOWLEDGE_ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=415, detail=f"Extension non autorisée : '{ext}'.")

            contents = await file.read()
            if len(contents) == 0:
                raise HTTPException(status_code=400, detail="Fichier vide.")
            if len(contents) > MAX_FILE_SIZE_BYTES:
                raise HTTPException(status_code=413, detail="Fichier trop volumineux.")
            if not _verify_magic(contents[:16], declared_mime):
                raise HTTPException(status_code=415, detail="Contenu ne correspond pas au type déclaré.")

            stored_filename = f"{uuid.uuid4().hex}{ext}"
            stored_path = os.path.join(KNOWLEDGE_UPLOAD_DIR, stored_filename)
            with open(stored_path, "wb") as fh:
                fh.write(contents)

            # Remove old file
            _safe_remove(existing.get("stored_path", ""))

            # Re-process
            try:
                raw_text = _extract_text(stored_path, declared_mime)
                clean = _clean_text(raw_text)
                effective_title = (title or existing.get("title", "")).strip()
                effective_filename = original_filename or existing.get("filename", "")
                chunk_texts, chunk_metas = _chunk_text(
                    text=clean,
                    doc_id=doc_id,
                    title=effective_title,
                    filename=effective_filename,
                )

                update_fields.update({
                    "filename": effective_filename,
                    "stored_filename": stored_filename,
                    "stored_path": stored_path,
                    "mime_type": declared_mime,
                    "size_bytes": len(contents),
                    "status": "active",
                    "chunk_count": len(chunk_texts),
                    "_chunk_texts": chunk_texts,
                    "_chunk_metadatas": chunk_metas,
                    "version": existing.get("version", 1) + 1,
                })
            except Exception as e:
                _safe_remove(stored_path)
                raise HTTPException(status_code=500, detail=f"Échec de l'extraction : {e}")

        await self.collection.update_one({"_id": oid}, {"$set": update_fields})

        # Rebuild FAISS if content changed
        if file is not None:
            await rebuild_faiss_with_knowledge(self.db)

        updated = await self.collection.find_one({"_id": oid}, projection={"_chunk_texts": 0, "_chunk_metadatas": 0})
        return self._format_out(updated)

    # ------------------------------------------------------------------
    # Archive / Delete
    # ------------------------------------------------------------------

    async def archive_document(self, doc_id: str) -> bool:
        """
        Archives a document: sets status='archived'.
        Triggers FAISS rebuild so archived content is no longer retrieved.
        """
        oid = ObjectId(doc_id) if ObjectId.is_valid(doc_id) else None
        if not oid:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        result = await self.collection.update_one(
            {"_id": oid},
            {"$set": {"status": "archived", "updated_at": datetime.utcnow()}}
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        # Rebuild FAISS so archived content is excluded
        await rebuild_faiss_with_knowledge(self.db)
        return True

    async def delete_document(self, doc_id: str) -> bool:
        """
        Hard-deletes a document (ADMIN only).
        Removes physical file, MongoDB record, and rebuilds FAISS.
        """
        oid = ObjectId(doc_id) if ObjectId.is_valid(doc_id) else None
        if not oid:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        doc = await self.collection.find_one({"_id": oid})
        if not doc:
            raise HTTPException(status_code=404, detail="Document introuvable.")

        _safe_remove(doc.get("stored_path", ""))
        await self.collection.delete_one({"_id": oid})

        # Rebuild FAISS so deleted content is no longer searchable
        await rebuild_faiss_with_knowledge(self.db)
        return True

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _format_out(doc: Optional[dict]) -> Optional[Dict[str, Any]]:
        if not doc:
            return None
        return {
            "id": str(doc["_id"]),
            "title": doc.get("title", ""),
            "filename": doc.get("filename", ""),
            "description": doc.get("description", ""),
            "document_type": doc.get("document_type", ""),
            "source": doc.get("source", "manual_upload"),
            "uploaded_by": doc.get("uploaded_by", ""),
            "uploader_name": doc.get("uploader_name", ""),
            "created_at": doc.get("created_at"),
            "updated_at": doc.get("updated_at"),
            "status": doc.get("status", "unknown"),
            "version": doc.get("version", 1),
            "chunk_count": doc.get("chunk_count", 0),
            "mime_type": doc.get("mime_type", ""),
            "size_bytes": doc.get("size_bytes", 0),
        }
