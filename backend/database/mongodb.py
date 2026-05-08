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

async def close_mongo_connection():
    logging.info("Closing MongoDB connection...")
    db.client.close()
    logging.info("MongoDB connection closed!")

def get_database():
    return db.db
