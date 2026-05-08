from datetime import datetime
from typing import Optional, List, Any
from bson import ObjectId


class MongoModel:
    @staticmethod
    def format_id(data: Any):
        """
        Normalizes MongoDB documents to always have both `_id` (str) and `id` (str) fields.
        Works for both freshly inserted documents (where _id may already be a string)
        and fetched documents (where _id is an ObjectId).
        """
        if isinstance(data, list):
            for item in data:
                if "_id" in item:
                    item["_id"] = str(item["_id"])
                    item["id"] = item["_id"]
            return data
        if data is not None and "_id" in data:
            data["_id"] = str(data["_id"])
            data["id"] = data["_id"]
        return data

    @staticmethod
    def to_object_id(id_str: str):
        try:
            return ObjectId(id_str)
        except Exception:
            return None
