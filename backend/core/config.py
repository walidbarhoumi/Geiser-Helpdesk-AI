import os
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    PROJECT_NAME: str = "ITSM Helpdesk API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # MongoDB
    MONGO_URL: str = os.getenv("MONGO_URL", "mongodb://localhost:27017")
    DATABASE_NAME: str = "itsm_helpdesk"
    
    # Security
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-super-secret-key-change-it-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Uploads
    UPLOAD_DIR: str = "uploads"
    
    # SMTP / Email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    FROM_EMAIL: str = os.getenv("FROM_EMAIL", "bwalid819@gmail.com")

    # IMAP / Inbound Email
    IMAP_ENABLED: bool = os.getenv("IMAP_ENABLED", "false").lower() in ("1", "true", "yes")
    IMAP_HOST: str = os.getenv("IMAP_HOST", "imap.gmail.com")
    IMAP_PORT: int = int(os.getenv("IMAP_PORT", "993"))
    IMAP_USER: str = os.getenv("IMAP_USER", "")
    IMAP_PASSWORD: str = os.getenv("IMAP_PASSWORD", "")
    IMAP_FOLDER: str = os.getenv("IMAP_FOLDER", "INBOX")
    IMAP_USE_SSL: bool = os.getenv("IMAP_USE_SSL", "true").lower() in ("1", "true", "yes")
    EMAIL_POLL_INTERVAL_MINUTES: int = int(os.getenv("EMAIL_POLL_INTERVAL_MINUTES", "3"))
    EMAIL_MAX_ATTACHMENT_MB: int = int(os.getenv("EMAIL_MAX_ATTACHMENT_MB", "10"))
    EMAIL_AUTO_PROVISION_USERS: bool = os.getenv("EMAIL_AUTO_PROVISION_USERS", "true").lower() in ("1", "true", "yes")
    
    # AI / Ollama
    OLLAMA_URL: str = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "gemma3:4b")

    # RAG / FAISS Knowledge Base
    RAG_DATABASE_PATH: str = os.getenv(
        "RAG_DATABASE_PATH",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "Database", "Chatbot First Database.txt"))
    )
    RAG_EMBEDDING_MODEL: str = os.getenv("RAG_EMBEDDING_MODEL", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
    RAG_INDEX_DIR: str = os.getenv(
        "RAG_INDEX_DIR",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "storage", "faiss"))
    )
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "3"))
    RAG_SCORE_THRESHOLD: float = float(os.getenv("RAG_SCORE_THRESHOLD", "0.30"))

    class Config:
        case_sensitive = True

settings = Settings()
