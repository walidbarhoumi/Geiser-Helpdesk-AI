from motor.motor_asyncio import AsyncIOMotorDatabase
from schemas.schemas import UserUpdate, UserRole, AgentCreate, TeamCreate
from models.base import MongoModel
from core.security import get_password_hash
from datetime import datetime


class UserService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.users

    async def get_users(self):
        cursor = self.collection.find()
        users = await cursor.to_list(length=100)
        return MongoModel.format_id(users)

    async def get_user_by_id(self, user_id: str):
        user = await self.collection.find_one({"_id": MongoModel.to_object_id(user_id)})
        return MongoModel.format_id(user)

    async def update_user(self, user_id: str, user_in: UserUpdate):
        update_data = user_in.dict(exclude_unset=True)
        if "password" in update_data:
            update_data["hashed_password"] = get_password_hash(update_data.pop("password"))

        await self.collection.update_one(
            {"_id": MongoModel.to_object_id(user_id)},
            {"$set": update_data}
        )
        return await self.get_user_by_id(user_id)

    async def delete_user(self, user_id: str):
        return await self.collection.delete_one({"_id": MongoModel.to_object_id(user_id)})


class AgentService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.agents

    async def create_agent(self, agent_in: AgentCreate):
        agent_dict = agent_in.dict()
        agent_dict["created_at"] = datetime.utcnow()
        # Update the linked user's role to AGENT
        await self.db.users.update_one(
            {"_id": MongoModel.to_object_id(agent_in.user_id)},
            {"$set": {"role": UserRole.AGENT.value}}
        )
        result = await self.collection.insert_one(agent_dict)
        agent_dict["_id"] = result.inserted_id
        return MongoModel.format_id(agent_dict)

    async def get_agents(self):
        cursor = self.collection.find()
        agents = await cursor.to_list(length=100)
        return MongoModel.format_id(agents)

    async def get_agent_by_id(self, agent_id: str):
        agent = await self.collection.find_one({"_id": MongoModel.to_object_id(agent_id)})
        return MongoModel.format_id(agent)

    async def update_agent(self, agent_id: str, update_data: dict):
        oid = MongoModel.to_object_id(agent_id)
        if not oid:
            return None
        
        agent = await self.collection.find_one({"_id": oid})
        if not agent:
            return None

        # Separate user updates vs agent updates
        user_updates = {}
        if "full_name" in update_data:
            user_updates["full_name"] = update_data.pop("full_name")
        if "email" in update_data:
            user_updates["email"] = update_data.pop("email")

        if user_updates:
            await self.db.users.update_one(
                {"_id": MongoModel.to_object_id(agent["user_id"])},
                {"$set": user_updates}
            )

        if update_data:
            await self.collection.update_one(
                {"_id": oid},
                {"$set": update_data}
            )
            
        return await self.get_agent_by_id(agent_id)

    async def delete_agent(self, agent_id: str):
        oid = MongoModel.to_object_id(agent_id)
        if not oid:
            return False
        result = await self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0


class TeamService:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db.teams

    async def create_team(self, team_in: TeamCreate):
        team_dict = team_in.dict()
        team_dict["created_at"] = datetime.utcnow()
        result = await self.collection.insert_one(team_dict)
        team_dict["_id"] = result.inserted_id
        return MongoModel.format_id(team_dict)

    async def get_teams(self):
        cursor = self.collection.find()
        teams = await cursor.to_list(length=100)
        return MongoModel.format_id(teams)

    async def add_agent_to_team(self, team_id: str, agent_id: str):
        await self.collection.update_one(
            {"_id": MongoModel.to_object_id(team_id)},
            {"$addToSet": {"agent_ids": agent_id}}
        )
        team = await self.collection.find_one({"_id": MongoModel.to_object_id(team_id)})
        return MongoModel.format_id(team)

    async def remove_agent_from_team(self, team_id: str, agent_id: str):
        await self.collection.update_one(
            {"_id": MongoModel.to_object_id(team_id)},
            {"$pull": {"agent_ids": agent_id}}
        )
        team = await self.collection.find_one({"_id": MongoModel.to_object_id(team_id)})
        return MongoModel.format_id(team)

    async def update_team(self, team_id: str, update_data: dict):
        oid = MongoModel.to_object_id(team_id)
        if not oid:
            return None
        
        if update_data:
            await self.collection.update_one(
                {"_id": oid},
                {"$set": update_data}
            )
        team = await self.collection.find_one({"_id": oid})
        return MongoModel.format_id(team)

    async def delete_team(self, team_id: str):
        oid = MongoModel.to_object_id(team_id)
        if not oid:
            return False
        result = await self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0
