import os
import sys

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiNotFound, ApiForbidden
from database import Database
from utils.broker_client import BrokerClient
from node.status import NodeStatus
from snapshot.status import SnapshotStatus
from utils.helper import convertProtobufToJSON

current = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(current)))

from validator_share_model.src.messages_queue import node_pb2

_LOGGER = get_logger(__name__)

class NodeHandler:
    def __init__(self, database: Database, broker_client: BrokerClient):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client

    async def get_nodes(self, user_info, skip=None, limit=None):
        query = { "user_id": user_info["user_id"] }
        nodes = await self.__database.find(collection=Database.NODES, query=query, skip=skip, limit=limit)
        count_nodes = await self.__database.count(collection=Database.NODES, query=query)
        return success({
            "nodes": nodes,
            "meta": {
                "offset": skip,
                "limit": limit,
                "total": count_nodes
            }
        })

    async def get_node(self, node_id):
        node = await self.__database.find_by_id(collection=Database.NODES, id=node_id)
        if node is None:
            return ApiNotFound("Node")
        return success(node)
    
    async def create_node(self, node, user_info):
        snapshot_id = node["snapshot_id"]
        snapshot_info = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        if snapshot_info is None:
            raise ApiBadRequest("Snapshot is not found")
        if ("status" not in snapshot_info) or (snapshot_info["status"] != SnapshotStatus.CREATED.name):
            raise ApiBadRequest("Snapshot is creating or created fail")

        node["network"] = snapshot_info.get("network", None)
        node["user_id"] = user_info["user_id"]
        node["status"] = NodeStatus.CREATE_PENDING.name
        created_id = await self.__database.create(collection=Database.NODES, new_document=node)

        routing_key = "driver.node.request.create_node"
        message = node_pb2.NodeCreateMessage()
        message.node_id = created_id
        message.node.name = node["name"]
        message.node.description = node.get("description", "")
        message.node.size_gigabytes = node.get("size_gigabytes", 0)
        message.node.tags.extend(node.get("tags", []))
        message.node.snapshot_cloud_id = snapshot_info["snapshot_cloud_id"]
        message.node.file_system_type = node.get("file_system_type", "")
        message.node.region = node.get("region", "")
        message.node.moniker = node["moniker"]
        message.node.network = node["network"]
        message.user.user_id = user_info["user_id"]
        messageJson = convertProtobufToJSON(message)
        reply_to = "validatorservice.events.create_node"
        await self.__broker_client.publish(routing_key, messageJson, reply_to)
        return success({
            "node_id": created_id,
            "status": NodeStatus.CREATE_PENDING.name
        })
    
    async def delete_node(self, node_id, user_info):
        existed_node = await self.__database.find_by_id(collection=Database.NODES, id=node_id)
        if existed_node is None:
            raise ApiBadRequest("Node is not found")
        if user_info["role"] != "admin" and user_info["user_id"] != existed_node["user_id"]:
            raise ApiForbidden("")
        if existed_node["status"] == NodeStatus.CREATE_PENDING.name:
            raise ApiBadRequest("Can not delete creating node")
        if existed_node["status"] in [NodeStatus.DELETE_PENDING.name, NodeStatus.DELETED.name]:
            raise ApiBadRequest("Node is deleted or deleting")

        modification = { "status": NodeStatus.DELETE_PENDING.name}
        await self.__database.update(collection=Database.NODES, id=node_id, modification=modification)

        routing_key = "driver.node.request.delete_node"
        message = node_pb2.NodeDeleteMessage()
        message.node_id = node_id
        messageJson = convertProtobufToJSON(message)
        reply_to = "validatorservice.events.delete_node"
        await self.__broker_client.publish(routing_key, messageJson, reply_to)

        return success({
            "node_id": node_id,
            "status": NodeStatus.DELETE_PENDING.name
        })