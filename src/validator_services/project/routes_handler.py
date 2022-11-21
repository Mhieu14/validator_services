import os
import json

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiNotFound, ApiForbidden
from database import Database
from utils.broker_client import BrokerClient
from node.routes_handler import NodeHandler
from project.status import ProjectStatus

_LOGGER = get_logger(__name__)

class ProjectHandler:
    def __init__(self, database, broker_client):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client
        self._node_handler = NodeHandler(database, broker_client)

    async def create_project(self, project, user_info):
        project["user_id"] = user_info["user_id"]
        project["status"] = ProjectStatus.CREATED.name
        created_id = await self.__database.create(collection=Database.PROJECTS, new_document=project)
        return success({
            "project": {
                "project_id": created_id,
                "status": ProjectStatus.CREATED.name
            }
        })

    async def delete_project(self, project_id, user_info):
        existed_project = await self.__database.find_by_id(collection=Database.PROJECTS, id=project_id)
        if existed_project is None:
            raise ApiBadRequest("Project is not found")
        if user_info["role"] != "admin" and user_info["user_id"] != existed_project["user_id"]:
            raise ApiForbidden("")
        if existed_project["status"] == ProjectStatus.DELETED.name:
            raise ApiBadRequest("Project is deleted")

        query = { "project_id": project_id }
        count_nodes = await self.__database.count(collection=Database.NODES, query=query)
        if (count_nodes > 0):
            raise ApiBadRequest("Project is not empty")

        modification = { "status": ProjectStatus.DELETED.name}
        await self.__database.update(collection=Database.PROJECTS, id=project_id, modification=modification)
        return success({
            "project": {
                "project_id": project_id,
                "status": ProjectStatus.DELETED.name
            }
        })

    async def get_projects(self, user_info, skip, limit):
        user_id = user_info["user_id"]
        query = { "user_id": user_id, "status": {"$ne": ProjectStatus.DELETED.name} }
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
        
    async def get_project(self, project_id, skip, limit, user_info):
        project = await self.__database.find_by_id(collection=Database.PROJECTS, id=project_id)
        # query = { "project_id": project_id }
        # nodes =  await self.__database.find(collection=Database.NODES, query=query, skip=skip, limit=limit)
        # count_nodes = await self.__database.count(collection=Database.NODES, query=query)
        if project is None:
            return ApiNotFound("Project")
        if user_info["role"] != "admin" and user_info["user_id"] != project["user_id"]:
            raise ApiForbidden("")
        nodes = await self._node_handler.get_nodes_data(project_id=project_id, skip=skip, limit=limit)
        project["nodes"] = nodes["nodes"]
        return success({
            "project": project,
            "meta": nodes["meta"]
        })