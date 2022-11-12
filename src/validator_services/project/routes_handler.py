import os
import json

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiNotFound
from database import Database
from utils.broker_client import BrokerClient
from node.routes_handler import NodeHandler

_LOGGER = get_logger(__name__)

class ProjectHandler:
    def __init__(self, database, broker_client):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client
        self._node_handler = NodeHandler(database, broker_client)

    async def create_project(self, project, user_info):
        project["user_id"] = user_info["user_id"]
        created_id = await self.__database.create(collection=Database.PROJECTS, new_document=project)
        return success({
            "project": {
                "project_id": created_id
            }
        })

    async def get_projects(self, user_info, skip, limit):
        user_id = user_info["user_id"]
        query = { "user_id": user_id }
        projects = await self.__database.find(collection=Database.PROJECTS, query=query, skip=skip, limit=limit)
        count_projects = await self.__database.count(collection=Database.PROJECTS, query=query)
        return success({
            "projects": projects,
            "meta": {
                "offset": skip,
                "limit": limit,
                "total": count_projects
            }
        })
        
    async def get_project(self, project_id, skip, limit):
        project = await self.__database.find_by_id(collection=Database.PROJECTS, id=project_id)
        # query = { "project_id": project_id }
        # nodes =  await self.__database.find(collection=Database.NODES, query=query, skip=skip, limit=limit)
        # count_nodes = await self.__database.count(collection=Database.NODES, query=query)
        if project is None:
            return ApiNotFound("Project")
        nodes = await self._node_handler.get_nodes_data(project_id=project_id, skip=skip, limit=limit)
        project["nodes"] = nodes["nodes"]
        return success({
            "project": project,
            "meta": nodes["meta"]
        })