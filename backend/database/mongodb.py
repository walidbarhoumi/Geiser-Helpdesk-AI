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


async def close_mongo_connection():
    logging.info("Closing MongoDB connection...")
    db.client.close()
    logging.info("MongoDB connection closed!")

def get_database():
    return db.db
