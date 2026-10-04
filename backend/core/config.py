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
    
    # Frontend & Reset Password
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    RESET_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("RESET_TOKEN_EXPIRE_MINUTES", "15"))

    # Rate Limiting (Requests count per window seconds)
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() in ("1", "true", "yes")
    RATE_LIMIT_LOGIN: int = int(os.getenv("RATE_LIMIT_LOGIN", "5"))
    RATE_LIMIT_LOGIN_WINDOW: int = int(os.getenv("RATE_LIMIT_LOGIN_WINDOW", "60"))
    RATE_LIMIT_2FA: int = int(os.getenv("RATE_LIMIT_2FA", "5"))
    RATE_LIMIT_2FA_WINDOW: int = int(os.getenv("RATE_LIMIT_2FA_WINDOW", "60"))
    RATE_LIMIT_PASSWORD_RESET: int = int(os.getenv("RATE_LIMIT_PASSWORD_RESET", "3"))
    RATE_LIMIT_PASSWORD_RESET_WINDOW: int = int(os.getenv("RATE_LIMIT_PASSWORD_RESET_WINDOW", "60"))
    RATE_LIMIT_AI: int = int(os.getenv("RATE_LIMIT_AI", "20"))
    RATE_LIMIT_AI_WINDOW: int = int(os.getenv("RATE_LIMIT_AI_WINDOW", "60"))
    RATE_LIMIT_GENERAL: int = int(os.getenv("RATE_LIMIT_GENERAL", "100"))
    RATE_LIMIT_GENERAL_WINDOW: int = int(os.getenv("RATE_LIMIT_GENERAL_WINDOW", "60"))
    TRUSTED_PROXIES: List[str] = [
        p.strip() for p in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1,testclient").split(",") if p.strip()
    ]

    # Uploads
    UPLOAD_DIR: str = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "uploads")
    )
    MAX_ATTACHMENT_SIZE_MB: int = int(os.getenv("MAX_ATTACHMENT_SIZE_MB", "10"))
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/gif",
        "text/plain",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/msword",
        "application/vnd.ms-excel",
    ]
    
    # SMTP / Email
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_TIMEOUT: int = int(os.getenv("SMTP_TIMEOUT", "15"))
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() in ("1", "true", "yes")
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() in ("1", "true", "yes")

    SMTP_USER: str = os.getenv("SMTP_USER", os.getenv("SMTP_USERNAME", "geiser.support@gmail.com"))
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    FROM_EMAIL: str = os.getenv("FROM_EMAIL", os.getenv("SMTP_FROM_EMAIL", "geiser.support@gmail.com"))

    # IMAP / Inbound Email-to-Ticket (STEP 8)
    EMAIL_TO_TICKET_ENABLED: bool = (
        os.getenv("EMAIL_TO_TICKET_ENABLED", os.getenv("IMAP_ENABLED", "false")).lower() in ("1", "true", "yes")
    )
    IMAP_ENABLED: bool = EMAIL_TO_TICKET_ENABLED
    EMAIL_IMAP_HOST: str = os.getenv("EMAIL_IMAP_HOST", os.getenv("IMAP_HOST", "imap.gmail.com"))
    IMAP_HOST: str = EMAIL_IMAP_HOST
    EMAIL_IMAP_PORT: int = int(os.getenv("EMAIL_IMAP_PORT", os.getenv("IMAP_PORT", "993")))
    IMAP_PORT: int = EMAIL_IMAP_PORT
    EMAIL_IMAP_USERNAME: str = os.getenv(
        "EMAIL_IMAP_USERNAME",
        os.getenv("IMAP_USER", os.getenv("SMTP_USER", "geiser.support@gmail.com"))
    )
    IMAP_USER: str = EMAIL_IMAP_USERNAME
    EMAIL_IMAP_PASSWORD: str = os.getenv(
        "EMAIL_IMAP_PASSWORD",
        os.getenv("IMAP_PASSWORD", os.getenv("SMTP_PASSWORD", ""))
    )
    IMAP_PASSWORD: str = EMAIL_IMAP_PASSWORD
    EMAIL_IMAP_USE_SSL: bool = (
        os.getenv("EMAIL_IMAP_USE_SSL", os.getenv("IMAP_USE_SSL", "true")).lower() in ("1", "true", "yes")
    )
    IMAP_USE_SSL: bool = EMAIL_IMAP_USE_SSL
    EMAIL_IMAP_FOLDER: str = os.getenv("EMAIL_IMAP_FOLDER", os.getenv("IMAP_FOLDER", "INBOX"))
    IMAP_FOLDER: str = EMAIL_IMAP_FOLDER

    EMAIL_POLL_INTERVAL_SECONDS: int = int(
        os.getenv("EMAIL_POLL_INTERVAL_SECONDS", str(int(os.getenv("EMAIL_POLL_INTERVAL_MINUTES", "3")) * 60))
    )
    EMAIL_POLL_INTERVAL_MINUTES: int = max(1, EMAIL_POLL_INTERVAL_SECONDS // 60)
    EMAIL_MARK_AS_READ: bool = os.getenv("EMAIL_MARK_AS_READ", "true").lower() in ("1", "true", "yes")
    EMAIL_MAX_MESSAGE_SIZE_MB: int = int(os.getenv("EMAIL_MAX_MESSAGE_SIZE_MB", "25"))
    EMAIL_MAX_ATTACHMENT_MB: int = int(os.getenv("EMAIL_MAX_ATTACHMENT_MB", "10"))
    EMAIL_AUTO_PROVISION_USERS: bool = os.getenv("EMAIL_AUTO_PROVISION_USERS", "true").lower() in ("1", "true", "yes")

    # Outbound Notification Reliability & Retry Engine
    NOTIFICATION_MAX_RETRIES: int = int(os.getenv("NOTIFICATION_MAX_RETRIES", "5"))
    NOTIFICATION_RETRY_INTERVAL_SECONDS: int = int(os.getenv("NOTIFICATION_RETRY_INTERVAL_SECONDS", "30"))
    NOTIFICATION_WORKER_INTERVAL_SECONDS: int = int(os.getenv("NOTIFICATION_WORKER_INTERVAL_SECONDS", "30"))

    # SLA Monitoring & Risk Evaluator
    SLA_SCAN_INTERVAL_MINUTES: int = int(os.getenv("SLA_SCAN_INTERVAL_MINUTES", "2"))
    
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

    # Twilio SMS Gateway
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")
    TWILIO_TEST_TO_NUMBER: str = os.getenv("TWILIO_TEST_TO_NUMBER", "")

    # LDAP / Active Directory Configuration
    LDAP_ENABLED: bool = os.getenv("LDAP_ENABLED", "false").lower() in ("1", "true", "yes")
    LDAP_SERVER: str = os.getenv("LDAP_SERVER", "ldap://localhost:389")
    LDAP_PORT: int = int(os.getenv("LDAP_PORT", "389"))
    LDAP_USE_SSL: bool = os.getenv("LDAP_USE_SSL", "false").lower() in ("1", "true", "yes")
    LDAP_USE_TLS: bool = os.getenv("LDAP_USE_TLS", "false").lower() in ("1", "true", "yes")
    LDAP_BASE_DN: str = os.getenv("LDAP_BASE_DN", "dc=geiser,dc=internal")
    LDAP_BIND_DN: str = os.getenv("LDAP_BIND_DN", "")
    LDAP_BIND_PASSWORD: str = os.getenv("LDAP_BIND_PASSWORD", "")
    LDAP_USER_SEARCH_BASE: str = os.getenv("LDAP_USER_SEARCH_BASE", "ou=Users,dc=geiser,dc=internal")
    LDAP_USER_SEARCH_FILTER: str = os.getenv("LDAP_USER_SEARCH_FILTER", "(&(objectClass=user)(|(sAMAccountName={username})(mail={username})))")
    LDAP_GROUP_SEARCH_BASE: str = os.getenv("LDAP_GROUP_SEARCH_BASE", "ou=Groups,dc=geiser,dc=internal")
    LDAP_TIMEOUT: int = int(os.getenv("LDAP_TIMEOUT", "5"))
    LDAP_DEFAULT_ROLE: str = os.getenv("LDAP_DEFAULT_ROLE", "USER")
    LDAP_TLS_CA_CERT_FILE: str = os.getenv("LDAP_TLS_CA_CERT_FILE", "")
    LDAP_TLS_VALIDATE_CERT: bool = os.getenv("LDAP_TLS_VALIDATE_CERT", "true").lower() in ("1", "true", "yes")

    # Role Mappings (comma-separated group names mapped to roles)
    LDAP_ROLE_GROUP_ADMIN: str = os.getenv("LDAP_ROLE_GROUP_ADMIN", "Helpdesk-Admins,Domain Admins")
    LDAP_ROLE_GROUP_SUPERVISOR: str = os.getenv("LDAP_ROLE_GROUP_SUPERVISOR", "Helpdesk-Supervisors")
    LDAP_ROLE_GROUP_AGENT: str = os.getenv("LDAP_ROLE_GROUP_AGENT", "Helpdesk-Agents,IT-Support")

    # Automated Backups & Disaster Recovery (STEP 6)
    BACKUP_ENABLED: bool = os.getenv("BACKUP_ENABLED", "true").lower() in ("1", "true", "yes")
    BACKUP_DIRECTORY: str = os.getenv(
        "BACKUP_DIRECTORY",
        os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backups"))
    )
    BACKUP_SCHEDULE_CRON: str = os.getenv("BACKUP_SCHEDULE_CRON", "0 2 * * *")  # Daily at 02:00 UTC
    BACKUP_RETENTION_DAYS: int = int(os.getenv("BACKUP_RETENTION_DAYS", "7"))
    BACKUP_RETENTION_WEEKLY: int = int(os.getenv("BACKUP_RETENTION_WEEKLY", "4"))
    BACKUP_RETENTION_MONTHLY: int = int(os.getenv("BACKUP_RETENTION_MONTHLY", "3"))
    BACKUP_COMPRESSION: bool = os.getenv("BACKUP_COMPRESSION", "true").lower() in ("1", "true", "yes")
    BACKUP_VERIFY_INTEGRITY: bool = os.getenv("BACKUP_VERIFY_INTEGRITY", "true").lower() in ("1", "true", "yes")
    BACKUP_MONGODB_DATABASE: str = os.getenv("BACKUP_MONGODB_DATABASE", "itsm_helpdesk")
    BACKUP_TIMEOUT_SECONDS: int = int(os.getenv("BACKUP_TIMEOUT_SECONDS", "300"))
    BACKUP_ALLOW_PRODUCTION_RESTORE: bool = os.getenv("BACKUP_ALLOW_PRODUCTION_RESTORE", "false").lower() in ("1", "true", "yes")
    MONGODUMP_PATH: str = os.getenv("MONGODUMP_PATH", "")
    MONGORESTORE_PATH: str = os.getenv("MONGORESTORE_PATH", "")

    class Config:
        case_sensitive = True
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

settings = Settings()
