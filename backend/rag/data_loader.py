# -*- coding: utf-8 -*-
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SupportTicketDocument(BaseModel):
    id: str
    category: str
    priority: str
    intent: str
    context: Dict[str, Any] = Field(default_factory=dict)
    conversation: List[List[str]] = Field(default_factory=list)
    sop: Optional[str] = None
    result: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    searchable_text: Optional[str] = None


class JSONLLoader:
    REQUIRED_FIELDS = {"id", "cat", "pri", "int", "ctx", "cv"}

    def __init__(self, file_path: Path):
        self.file_path = Path(file_path).resolve()

    def load(self) -> List[SupportTicketDocument]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Fichier de base de connaissances introuvable : {self.file_path}")

        documents: List[SupportTicketDocument] = []
        line_num = 0
        skipped = 0

        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                line_num += 1
                stripped = line.strip()
                if not stripped:
                    continue

                try:
                    data = json.loads(stripped)
                except Exception as err:
                    logger.warning(f"Ligne {line_num} ignoree (JSON invalide) : {err}")
                    skipped += 1
                    continue

                missing = self.REQUIRED_FIELDS - set(data.keys())
                if missing:
                    logger.warning(f"Ligne {line_num} ignoree (champs manquants : {missing})")
                    skipped += 1
                    continue

                doc = SupportTicketDocument(
                    id=str(data.get("id", f"UNKNOWN-{line_num}")),
                    category=str(data.get("cat", "")),
                    priority=str(data.get("pri", "")),
                    intent=str(data.get("int", "")),
                    context=data.get("ctx", {}) if isinstance(data.get("ctx"), dict) else {},
                    conversation=data.get("cv", []) if isinstance(data.get("cv"), list) else [],
                    sop=data.get("sop"),
                    result=data.get("res"),
                    tags=data.get("tg", []) if isinstance(data.get("tg"), list) else []
                )
                documents.append(doc)

        logger.info(
            f"Chargement JSONL reussi : {len(documents)} documents charges depuis {self.file_path} (lignes ignorees : {skipped})"
        )
        return documents
