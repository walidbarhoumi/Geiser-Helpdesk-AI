from motor.motor_asyncio import AsyncIOMotorClient
from core.config import settings
import logging

class Database:
    client: AsyncIOMotorClient = None
    db = None

db = Database()

async def connect_to_mongo():
    logging.info("Connecting to MongoDB...")
    db.client = AsyncIOMotorClient(settings.MONGO_URL)
    db.db = db.client[settings.DATABASE_NAME]
    logging.info("Connected to MongoDB!")

    # Ensure indexes for password_resets collection
    try:
        # TTL index on expires_at: automatically remove expired records after expiration
        await db.db.password_resets.create_index("expires_at", expireAfterSeconds=0)
        # Fast query lookup on token_hash
        await db.db.password_resets.create_index("token_hash", unique=True)
        # Fast lookup by user_id
        await db.db.password_resets.create_index("user_id")
        logging.info("Indexes for password_resets configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating password_resets indexes: {e}")

    # Ensure indexes for token_blacklist collection (JWT revocation)
    try:
        # TTL index on expires_at: automatically remove expired blacklist records once token lifetime ends
        await db.db.token_blacklist.create_index("expires_at", expireAfterSeconds=0)
        # Fast unique lookup on jti
        await db.db.token_blacklist.create_index("jti", unique=True)
        # Lookup by user_id for auditing / revoking all user sessions
        await db.db.token_blacklist.create_index("user_id")
        logging.info("Indexes for token_blacklist configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating token_blacklist indexes: {e}")

    # Ensure indexes for attachments collection (ticket file attachments)
    try:
        # Primary lookup: all attachments for a given ticket
        await db.db.attachments.create_index("ticket_id")
        # Secondary lookup: single attachment by ticket_id + _id (covered query)
        await db.db.attachments.create_index([("ticket_id", 1), ("_id", 1)])
        # Sort by upload date
        await db.db.attachments.create_index("created_at")
        logging.info("Indexes for attachments configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating attachments indexes: {e}")

    # Ensure indexes for rate_limits collection (distributed rate limiting)
    try:
        # TTL index: automatically remove expired rate limit windows
        await db.db.rate_limits.create_index("expires_at", expireAfterSeconds=0)
        # Fast unique lookup by key
        await db.db.rate_limits.create_index("key", unique=True)
        logging.info("Indexes for rate_limits configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating rate_limits indexes: {e}")

    # Ensure indexes for routing_history collection (historical routing learning)
    try:
        # Fast lookup: all routing records for a given ticket
        await db.db.routing_history.create_index("ticket_id")
        # Fast lookup: all routing records for a given agent (for historical score computation)
        await db.db.routing_history.create_index("assigned_agent_id")
        # Composite: agent performance within a category/subcategory
        await db.db.routing_history.create_index([("category", 1), ("subcategory", 1)])
        # Time-based sorting for time decay scoring
        await db.db.routing_history.create_index("created_at")
        # Filter by routing method (automatic, manual, reassignment, ai, fallback)
        await db.db.routing_history.create_index("routing_method")
        logging.info("Indexes for routing_history configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating routing_history indexes: {e}")

    # Ensure indexes for knowledge_documents collection (dynamic RAG ingestion)
    try:
        # Filter by document status (active, processing, archived, failed)
        await db.db.knowledge_documents.create_index("status")
        # Sort by creation date
        await db.db.knowledge_documents.create_index("created_at")
        # Fast lookup by uploader user_id
        await db.db.knowledge_documents.create_index("uploaded_by")
        # Search by title
        await db.db.knowledge_documents.create_index("title")
        logging.info("Indexes for knowledge_documents configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating knowledge_documents indexes: {e}")

    # Ensure indexes for SLA Risk Detection & Alert deduplication (STEP 4)
    try:
        # Fast query for active tickets by status and SLA deadline
        await db.db.tickets.create_index([("status", 1), ("sla_deadline", 1)])
        # Fast lookup for SLA status queue
        await db.db.tickets.create_index([("sla_status", 1), ("status", 1)])

        # Strict compound idempotency index to prevent duplicate SLA alert dispatches
        await db.db.sla_alerts.create_index(
            [("ticket_id", 1), ("alert_type", 1), ("threshold_id", 1), ("recipient_id", 1), ("channel", 1)],
            unique=True
        )
        await db.db.sla_alerts.create_index("created_at")
        await db.db.sla_alerts.create_index("ticket_id")

        # Configuration uniqueness
        await db.db.sla_risk_config.create_index("key", unique=True)
        logging.info("Indexes for SLA risk monitoring configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating SLA risk monitoring indexes: {e}")

    # Ensure indexes for backups collection (STEP 6 Automated Backups & Disaster Recovery)
    try:
        # Fast unique lookup by backup_id
        await db.db.backups.create_index("backup_id", unique=True)
        # Chronological sorting for retention management and history listing
        await db.db.backups.create_index("created_at")
        # Filter by status (RUNNING, SUCCESS, FAILED, CORRUPTED, DELETED)
        await db.db.backups.create_index("status")
        # Filter by retention class (DAILY, WEEKLY, MONTHLY)
        await db.db.backups.create_index("retention_class")
        logging.info("Indexes for backups collection configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating backups indexes: {e}")

    # Ensure indexes for processed_emails collection (STEP 8 Inbound Email-to-Ticket & Threading)
    try:
        # Strict uniqueness on Message-ID to guarantee idempotency across duplicate fetches
        await db.db.processed_emails.create_index("message_id", unique=True)
        # Fast query by associated ticket_id
        await db.db.processed_emails.create_index("ticket_id")
        # Query by processing status (RECEIVED, PROCESSING, PROCESSED, FAILED, DEAD_LETTER)
        await db.db.processed_emails.create_index("status")
        # Index on in_reply_to and references for high-speed threading resolution
        await db.db.processed_emails.create_index("in_reply_to")
        await db.db.processed_emails.create_index("references")
        await db.db.processed_emails.create_index("received_at")
        logging.info("Indexes for processed_emails configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating processed_emails indexes: {e}")

    # Ensure indexes for notifications collection (STEP 8 Outbound Reliability & Worker Queue)
    try:
        # Worker queue index: filter pending/retrying notifications ready to send
        await db.db.notifications.create_index([("status", 1), ("next_retry_at", 1)])
        # Fast lookup by idempotency_key to prevent duplicate outbound dispatches
        await db.db.notifications.create_index("idempotency_key", unique=True, sparse=True)
        await db.db.notifications.create_index("channel")
        await db.db.notifications.create_index("created_at")
        logging.info("Indexes for notifications reliability queue configured successfully.")
    except Exception as e:
        logging.warning(f"Warning creating notifications queue indexes: {e}")



async def close_mongo_connection():
    logging.info("Closing MongoDB connection...")
    db.client.close()
    logging.info("MongoDB connection closed!")

def get_database():
    return db.db
