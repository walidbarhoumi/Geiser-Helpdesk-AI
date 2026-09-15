# -*- coding: utf-8 -*-
from pathlib import Path
from core.config import settings

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = Path(settings.RAG_DATABASE_PATH).resolve()
DEFAULT_INDEX_DIR = Path(settings.RAG_INDEX_DIR).resolve()
FAISS_INDEX_FILE = DEFAULT_INDEX_DIR / 'index.faiss'
METADATA_FILE = DEFAULT_INDEX_DIR / 'metadata.json'

# Model & Retrieval
EMBEDDING_MODEL_NAME = settings.RAG_EMBEDDING_MODEL
DEFAULT_TOP_K = settings.RAG_TOP_K
DEFAULT_SCORE_THRESHOLD = settings.RAG_SCORE_THRESHOLD
