import asyncio
import resource
import motor.motor_asyncio as aiomotor
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import ServerSelectionTimeoutError

from config import DBConfig
from utils.logging import get_logger

_LOGGER = get_logger(__name__)

class Database:
    def __init__(self):
        self._mongo_uri = f"mongodb://{DBConfig.USERNAME}:{DBConfig.PASSWORD}@{DBConfig.HOST}:{DBConfig.PORT}"
        self._dbname = DBConfig.DATABASE
        self._conn = None

    async def connect(self):
        _LOGGER.info("Connecting to database")
        try:
            self._conn = aiomotor.AsyncIOMotorClient(self._mongo_uri)[self._dbname]
            _LOGGER.info(f"List collection: {await self._conn.list_collection_names()}")
            _LOGGER.info("Successfully connected to the database")
            return
        except ServerSelectionTimeoutError:
            _LOGGER.error("Cannot connect to the database")
            raise ServerSelectionTimeoutError
            
        
    async def create_snapshot(self, new_snapshot):
        result = await self._conn["snapshots"].insert_ont(new_snapshot)
        snapshot_id = str(result.inserted_id)
        return snapshot_id

    async def get_snapshots(self, **kwargs):
        if "snapshot_id" in kwargs:
            kwargs["_id"] = ObjectId(kwargs["snapshot_id"])
            del kwargs["snapshot_id"]
        cursor = self._conn["snapshot"].find(kwargs)
        snapshots = []
        async for snapshot in cursor:
            snapshot["snapshot_id"] = str(snapshot["_id"])
            snapshot.pop("_id", None)
            snapshots.append(snapshot)
        return snapshots