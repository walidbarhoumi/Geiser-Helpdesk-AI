# -*- coding: utf-8 -*-
import logging
import threading
from typing import List, Union
import numpy as np
from sentence_transformers import SentenceTransformer
from rag.config import EMBEDDING_MODEL_NAME

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Singleton thread-safe pour le modèle d'embeddings multilingue Sentence Transformers.
    Assure un chargement unique en mémoire vive et la normalisation L2 des vecteurs.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, model_name: str = EMBEDDING_MODEL_NAME):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(EmbeddingService, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME):
        if getattr(self, "_initialized", False):
            return

        self.model_name = model_name
        logger.info(f"Chargement du modèle d'embeddings multilingue : '{self.model_name}'...")
        try:
            self.model = SentenceTransformer(self.model_name)
            # Test dimension
            dummy_emb = self.model.encode(["test"], normalize_embeddings=True)
            self.embedding_dimension = int(dummy_emb.shape[1])
            self._initialized = True
            logger.info(
                f"Modèle d'embeddings prêt : '{self.model_name}' (dimension={self.embedding_dimension})"
            )
        except Exception as e:
            logger.error(f"Échec critique du chargement du modèle d'embeddings '{self.model_name}' : {e}")
            raise RuntimeError(f"Impossible de charger SentenceTransformer '{self.model_name}' : {e}")

    def encode(self, texts: Union[str, List[str]], normalize: bool = True) -> np.ndarray:
        """
        Calcule les embeddings pour un texte unique ou une liste de textes.
        Retourne un tableau numpy float32 normalisé L2.
        """
        if isinstance(texts, str):
            texts = [texts]

        if not texts:
            return np.empty((0, self.embedding_dimension), dtype=np.float32)

        raw_vectors = self.model.encode(
            texts,
            normalize_embeddings=normalize,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        return raw_vectors.astype(np.float32)
