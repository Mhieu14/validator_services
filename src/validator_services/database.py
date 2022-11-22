import asyncio
import resource
import string
import motor.motor_asyncio as aiomotor

from datetime import datetime, timezone
from typing import Collection
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from datetime import datetime
from pymongo.errors import ServerSelectionTimeoutError

from config import DBConfig
from utils.logging import get_logger
from utils.helper import get_current_isodate

_LOGGER = get_logger(__name__)

class Database:
    def __init__(self):
        self._mongo_uri = f"mongodb://{DBConfig.USERNAME}:{DBConfig.PASSWORD}@{DBConfig.HOST}:{DBConfig.PORT}"
        # self._mongo_uri = "mongodb+srv://user1:my-secret-pw@cluster0.wjqj9.mongodb.net/?retryWrites=true&w=majority"
        self._dbname = DBConfig.DATABASE
        self._conn = None

    async def connect(self):
        _LOGGER.info("Connecting to database")
        try:
            self._conn = aiomotor.AsyncIOMotorClient(self._mongo_uri)[self._dbname]
            _LOGGER.info(f"List collection: {await self._conn.list_collection_names()}")
            _LOGGER.info("Successfully connected to the database")
            return
        except ServerSelectionTimeoutError as error:
            _LOGGER.error("Cannot connect to the database")
            print(error)
            raise ServerSelectionTimeoutError

    PROJECTS = "projects"
    SNAPSHOTS = "snapshots"
    NODES = "nodes"
    NETWORKS_SETUP_CONFIG = "networks_setup_config"
    COLLECTIONS_ID = {
        PROJECTS: "project_id",
        SNAPSHOTS: "snapshot_id",
        NODES: "node_id"
    }
    
    async def create(self, collection: string, new_document: dict):
        new_document["created_at"] = datetime.now(tz=timezone.utc)
        result = await self._conn[collection].insert_one(new_document)
        inserted_id = str(result.inserted_id)
        return inserted_id
        
    async def find(self, collection: string, query: dict = {}, skip=None, limit=None):
        if not skip and not limit:
            cursor = self._conn[collection].find(query).sort("_id", -1)
        else:
            cursor = self._conn[collection].find(query).sort("_id", -1).skip(skip).limit(limit)
        result = []
        async for document in cursor:
            document[self.COLLECTIONS_ID[collection]] = str(document["_id"])
            document.pop("_id", None)
            result.append(document)
        return result

    async def count(self, collection: string, query: dict = None):
        count = await self._conn[collection].count_documents(query)
        return count

    async def find_by_id(self, collection: string, id: string):
        try:
            query = {  "_id": ObjectId(id) }
        except:
            return None
        document = await self._conn[collection].find_one(query)
        if document is None:
            print("Invalid dou")
            return None 
        document[self.COLLECTIONS_ID[collection]] = str(document["_id"])
        document.pop("_id", None)
        return document

    async def find_one(self, collection: string, query: dict):
        document = await self._conn[collection].find_one(query)
        if document is None:
            print("Invalid dou")
            return None
        document[self.COLLECTIONS_ID[collection]] = str(document["_id"])
        document.pop("_id", None)
        return document

    async def update(self, collection: string, id: string, modification: dict, unset: dict = None):
        filter = {
            "_id": ObjectId(id)
        }
        # add datetime here
        update = {}
        if modification:
            update['$set'] = modification
        if unset:
            update['$unset'] = unset
        updated = await self._conn[collection].find_one_and_update(filter,
                                                                    update=update,
                                                                    return_document=ReturnDocument.AFTER)
        if updated is None:
            return None
        updated[self.COLLECTIONS_ID[collection]] = str(updated["_id"])
        updated.pop("_id", None)
        return updated

    async def update_many(self, collection: string, query: string, modification: dict, unset: dict = None):
        update = {}
        if modification:
            update['$set'] = modification
        if unset:
            update['$unset'] = unset
        updated = await self._conn[collection].update_many(query, update=update)
        return updated

    async def find_setup_configs_by_network(self, network):
        query = { "network": network }
        document = await self._conn[self.NETWORKS_SETUP_CONFIG].find_one(query)
        if document is None:
            print("Invalid dou")
            return None
        document.pop("_id", None)
        return document

    async def find_all_network(self):
        cursor = self._conn[self.NETWORKS_SETUP_CONFIG].find()
        result = []
        async for document in cursor:
            document.pop("_id", None)
            result.append(document)
        return result
