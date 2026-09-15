# -*- coding: utf-8 -*-
import json
import logging
import os
import shutil
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
import faiss
import numpy as np

from rag.config import DEFAULT_INDEX_DIR, FAISS_INDEX_FILE, METADATA_FILE

logger = logging.getLogger(__name__)


class FAISSVectorIndex:
    """
    Gestionnaire d'index vectoriel FAISS persistant basé sur IndexFlatIP (produit scalaire)
    avec sauvegarde synchronisée des métadonnées JSON.
    """

    def __init__(self, index_dir: Path = DEFAULT_INDEX_DIR):
        self.index_dir = Path(index_dir).resolve()
        self.index_file = self.index_dir / "index.faiss"
        self.metadata_file = self.index_dir / "metadata.json"
        self.index: Optional[faiss.Index] = None
        self.metadata: List[Dict[str, Any]] = []

    def is_ready(self) -> bool:
        """Vérifie si l'index en mémoire est chargé et non vide."""
        return self.index is not None and self.index.ntotal > 0 and len(self.metadata) == self.index.ntotal

    def exists_on_disk(self) -> bool:
        """Vérifie si l'index et les métadonnées existent sur le disque."""
        return self.index_file.exists() and self.metadata_file.exists()

    def build_index(
        self,
        embeddings: np.ndarray,
        metadatas: List[Dict[str, Any]]
    ) -> None:
        """
        Construit un nouvel index FAISS en mémoire à partir d'embeddings normalisés.
        """
        if embeddings.shape[0] != len(metadatas):
            raise ValueError(
                f"Incohérence : {embeddings.shape[0]} embeddings reçus mais {len(metadatas)} métadonnées fournies."
            )

        dimension = embeddings.shape[1]
        logger.info(f"Construction de l'index FAISS FlatIP (dim={dimension}, {len(metadatas)} vecteurs)...")

        index = faiss.IndexFlatIP(dimension)
        index.add(embeddings.astype(np.float32))

        self.index = index
        self.metadata = metadatas
        logger.info(f"Index FAISS construit avec succès : {self.index.ntotal} éléments.")

    def save(self) -> None:
        """
        Sauvegarde atomique de l'index FAISS et des métadonnées sur le disque.
        """
        if self.index is None or not self.metadata:
            raise ValueError("Aucun index ou métadonnées à sauvegarder.")

        self.index_dir.mkdir(parents=True, exist_ok=True)

        # Fichiers temporaires pour écriture atomique
        tmp_index = self.index_dir / "index.faiss.tmp"
        tmp_meta = self.index_dir / "metadata.json.tmp"

        try:
            faiss.write_index(self.index, str(tmp_index))
            with open(tmp_meta, "w", encoding="utf-8") as f:
                json.dump(self.metadata, f, ensure_ascii=False, indent=2)

            # Remplacement atomique
            if tmp_index.exists():
                shutil.move(str(tmp_index), str(self.index_file))
            if tmp_meta.exists():
                shutil.move(str(tmp_meta), str(self.metadata_file))

            logger.info(f"Index FAISS et métadonnées sauvegardés avec succès dans : {self.index_dir}")
        except Exception as e:
            if tmp_index.exists():
                tmp_index.unlink()
            if tmp_meta.exists():
                tmp_meta.unlink()
            logger.error(f"Erreur lors de la sauvegarde de l'index FAISS : {e}")
            raise

    def load(self) -> bool:
        """
        Charge l'index FAISS et les métadonnées depuis le disque.
        Retourne True en cas de succès, False sinon.
        """
        if not self.exists_on_disk():
            logger.warning(f"Fichiers d'index introuvables dans {self.index_dir}")
            return False

        try:
            logger.info(f"Chargement de l'index FAISS depuis {self.index_file}...")
            self.index = faiss.read_index(str(self.index_file))

            with open(self.metadata_file, "r", encoding="utf-8") as f:
                self.metadata = json.load(f)

            if self.index.ntotal != len(self.metadata):
                logger.error(
                    f"Désynchronisation critique : index FAISS a {self.index.ntotal} vecteurs "
                    f"mais metadata.json contient {len(self.metadata)} entrées."
                )
                return False

            logger.info(f"Index FAISS chargé avec succès : {self.index.ntotal} éléments synchronisés.")
            return True
        except Exception as e:
            logger.error(f"Échec du chargement de l'index FAISS : {e}")
            return False

    def search(
        self,
        query_vector: np.ndarray,
        top_k: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Effectue une recherche des k vecteurs les plus proches.
        Retourne : (scores, indices)
        """
        if not self.is_ready():
            if not self.load():
                raise RuntimeError("L'index FAISS n'est pas initialisé ou n'a pas pu être chargé.")

        if query_vector.ndim == 1:
            query_vector = np.expand_dims(query_vector, axis=0)

        top_k = min(top_k, self.index.ntotal)
        scores, indices = self.index.search(query_vector.astype(np.float32), top_k)
        return scores[0], indices[0]
