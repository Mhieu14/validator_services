import os
import json

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiInternalError
from database import Database
from utils.broker_client import BrokerClient

_LOGGER = get_logger(__name__)

class ProjectHandler:
    def __init__(self, database, broker_client):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client

    async def create_project(self, project, user_info):
        project["user_id"] = user_info["user_id"]
        created_id = await self.__database.create(collection=Database.PROJECTS, new_document=project)
        return success({
            "id": created_id
        })

    async def get_projects(self, user_id):
        query = { "user_id": user_id }
        snapshots = await self.__database.find(collection=Database.PROJECTS, query=query)
        return success(snapshots)
        