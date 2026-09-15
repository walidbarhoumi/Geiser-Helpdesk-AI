# -*- coding: utf-8 -*-
import sys
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

# Ajouter le répertoire backend au sys.path si exécuté directement
current_file = Path(__file__).resolve()
backend_dir = current_file.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from rag.config import DEFAULT_DATABASE_PATH, DEFAULT_INDEX_DIR
from rag.data_loader import JSONLLoader
from rag.document_processor import DocumentProcessor
from rag.embeddings import EmbeddingService
from rag.faiss_index import FAISSVectorIndex

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("rag.indexer")


class RAGIndexer:
    """
    Service complet de construction et régénération de l'index vectoriel FAISS.
    """

    def __init__(
        self,
        db_path: Optional[Path] = None,
        index_dir: Optional[Path] = None
    ):
        self.db_path = Path(db_path or DEFAULT_DATABASE_PATH).resolve()
        self.index_dir = Path(index_dir or DEFAULT_INDEX_DIR).resolve()
        self.loader = JSONLLoader(self.db_path)
        self.embeddings = EmbeddingService()
        self.vector_index = FAISSVectorIndex(self.index_dir)

    def rebuild_index(self) -> Dict[str, Any]:
        """
        Exécute la chaîne complète d'indexation :
        1. Lecture du JSONL
        2. Formatage des documents
        3. Calcul des embeddings
        4. Construction de l'index FAISS
        5. Sauvegarde atomique sur disque
        """
        logger.info(f"=== Début de la réindexation RAG ===")
        logger.info(f"Source de données : {self.db_path}")
        logger.info(f"Répertoire cible : {self.index_dir}")

        if not self.db_path.exists():
            raise FileNotFoundError(f"Fichier de base de connaissances introuvable : {self.db_path}")

        # 1. Chargement
        documents = self.loader.load()
        if not documents:
            raise ValueError(f"Aucun document valide trouvé dans {self.db_path}")

        # 2. Formatage
        texts, metadatas = DocumentProcessor.process_documents(documents)

        # 3. Embeddings
        logger.info(f"Génération des embeddings pour {len(texts)} documents...")
        vectors = self.embeddings.encode(texts, normalize=True)

        # 4. Construction FAISS
        self.vector_index.build_index(vectors, metadatas)

        # 5. Persistance atomique
        self.vector_index.save()

        summary = {
            "status": "success",
            "indexed_count": len(documents),
            "vector_dimension": vectors.shape[1],
            "database_path": str(self.db_path),
            "index_path": str(self.index_dir)
        }
        logger.info(f"=== Réindexation RAG terminée avec succès : {summary} ===")
        return summary


def main():
    indexer = RAGIndexer()
    try:
        res = indexer.rebuild_index()
        print(f"\nIndexation réussie : {res['indexed_count']} documents indexés avec succès.")
    except Exception as e:
        print(f"\nErreur critique lors de l'indexation : {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
