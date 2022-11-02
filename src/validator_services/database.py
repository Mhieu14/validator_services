import asyncio
from enum import Enum
import resource
import string
from typing import Collection
import motor.motor_asyncio as aiomotor
from bson.objectid import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import ServerSelectionTimeoutError

from config import DBConfig
from utils.logging import get_logger

_LOGGER = get_logger(__name__)

class Database:
    def __init__(self):
        # self._mongo_uri = f"mongodb://{DBConfig.USERNAME}:{DBConfig.PASSWORD}@{DBConfig.HOST}:{DBConfig.PORT}"
        self._mongo_uri = "mongodb+srv://user1:my-secret-pw@cluster0.wjqj9.mongodb.net/?retryWrites=true&w=majority"
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
    COLLECTIONS_ID = {
        PROJECTS: "project_id",
        SNAPSHOTS: "snapshot_id",
        NODES: "node_id"
    }
    
    async def create(self, collection: string, new_document: dict):
        # add datetime here
        result = await self._conn[collection].insert_one(new_document)
        inserted_id = str(result.inserted_id)
        return inserted_id
        
    async def find(self, collection: string, query: dict = {}, skip=None, limit=None):
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
