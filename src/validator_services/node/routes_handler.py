import os
import sys
import json

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

def convert_node_to_output(node):
    fullnode_info = node.get("fullnode_info")
    return {
        "project_id": node.get("project_id"),
        "node_id": node["node_id"],
        "network": node["network"],
        "moniker": node["moniker"],
        "status": node["status"],
        "message": node.get("message"),
        "created_at": node.get("create_processed_at"),
        "address": None if fullnode_info == None else fullnode_info.get("ValidatorInfo", {}).get("Address"),
        "public_key": None if fullnode_info == None else fullnode_info.get("ValidatorInfo", {}).get("PubKey", {}).get("value")
    }
class NodeHandler:
    def __init__(self, database: Database, broker_client: BrokerClient):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client

    async def get_nodes_data(self, user_info={}, project_id=None, skip=None, limit=None):
        query = {   
            "status": {"$ne": NodeStatus.DELETED.name}
        }
        if "user_id" in user_info:
            query["user_id"] = user_info["user_id"]
        if project_id is not None:
            query["project_id"] = project_id
        nodes = await self.__database.find(collection=Database.NODES, query=query, skip=skip, limit=limit)
        count_nodes = await self.__database.count(collection=Database.NODES, query=query)
        nodes_output = []
        for node in nodes:
            nodes_output.append(convert_node_to_output(node))
        return {
            "nodes": nodes_output,
            "meta": {
                "offset": skip,
                "limit": limit,
                "total": count_nodes
            }
        }

    async def get_nodes(self, user_info={}, project_id=None, skip=None, limit=None):
        nodes_data = await self.get_nodes_data(user_info, project_id, skip, limit)
        return success(nodes_data)

    async def get_node(self, node_id, user_info):
        node = await self.__database.find_by_id(collection=Database.NODES, id=node_id)
        if node is None:
            return ApiNotFound("Node")
        if user_info["role"] != "admin" and user_info["user_id"] != node["user_id"]:
            raise ApiForbidden("")
        return success({
            "node": convert_node_to_output(node)
        })

    async def send_message_create_node(self, node, node_id, user_info, snapshot_info, setup_config):
        routing_key = "driver.node.request.create_node"
        message = node_pb2.NodeCreateMessage()
        message.node_id = node_id
        message.node.description = node.get("description", "")
        message.node.size_gigabytes = node.get("size_gigabytes", 0)
        message.node.tags.extend(node.get("tags", []))
        message.node.snapshot_cloud_id = snapshot_info["snapshot_cloud_id"]
        message.node.file_system_type = node.get("file_system_type", "")
        message.node.region = node.get("region", "")
        message.node.moniker = node["moniker"]
        message.node.network = node["network"]
        message.user.user_id = user_info["user_id"]
        message.setup_config.network = setup_config["network"]
        message.setup_config.setup_file_url = setup_config["setup_file_url"]
        message.setup_config.setup_file_name = setup_config["setup_file_name"]
        message.setup_config.container_name = setup_config["container_name"]
        message.setup_config.status_command = setup_config["status_command"]
        message.setup_config.default_droplet_size = setup_config["default_droplet_size"]
        message.setup_config.env.node_moniker = setup_config["env"]["node_moniker"]
        message.setup_config.env.volume_name = setup_config["env"]["volume_name"]
        if ("droplet_size" in node):
            message.node.droplet_size = node.get("droplet_size")
        messageJson = convertProtobufToJSON(message)
        reply_to = "validatorservice.events.create_node"
        await self.__broker_client.publish(routing_key, messageJson, reply_to)
        return
    
    async def create_node(self, node, user_info):
        project_info = await self.__database.find_by_id(collection=Database.PROJECTS, id=node["project_id"])
        if project_info is None or project_info.get("user_id") != user_info["user_id"]:
            raise ApiBadRequest("Project is not found")

        snapshot_info = None
        if ("snapshot_id" in node):
            snapshot_id = node["snapshot_id"]
            snapshot_info = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        else:
            snapshot_info = await self.__database.find_snapshot_by_network(network=node["network"])
        if snapshot_info is None:
            raise ApiBadRequest("Snapshot is not found")
        if ("status" not in snapshot_info) or (snapshot_info["status"] != SnapshotStatus.CREATED.name):
            raise ApiBadRequest("Snapshot is not created")

        node["snapshot_id"] = snapshot_info["snapshot_id"]
        node["network"] = snapshot_info["network"]
        node["user_id"] = user_info["user_id"]
        node["status"] = NodeStatus.CREATE_PENDING.name
        created_id = await self.__database.create(collection=Database.NODES, new_document=node)

        setup_config = await self.__database.find_setup_configs_by_network(network=snapshot_info["network"])
        await self.send_message_create_node(node=node, node_id=created_id, user_info=user_info, snapshot_info=snapshot_info, setup_config=setup_config)
        return success({
            "node": {
                "node_id": created_id,
                "status": NodeStatus.CREATE_PENDING.name
            }
        })
    
    async def retry_create_node(self, node_id, user_info):
        existed_node = await self.__database.find_by_id(collection=Database.NODES, id=node_id)
        if existed_node is None:
            raise ApiBadRequest("Node is not found")
        if user_info["role"] != "admin" and user_info["user_id"] != existed_node["user_id"]:
            raise ApiForbidden("")
        if existed_node["status"] != NodeStatus.CREATE_FAIL.name:
            raise ApiBadRequest("Only create fail node allow to retry create")

        modification = { "status": NodeStatus.CREATE_RETRYING.name}
        await self.__database.update(collection=Database.NODES, id=node_id, modification=modification)

        setup_config = await self.__database.find_setup_configs_by_network(network=snapshot_info["network"])
        if "create_process" not in existed_node:
            snapshot_id = existed_node["snapshot_id"]
            snapshot_info = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
            await self.send_message_create_node(node=existed_node, node_id=node_id, user_info=user_info, snapshot_info=snapshot_info, setup_config=setup_config)
        else:
            routing_key = "driver.node.request.retry_create_node"
            message = {
                "node_id": node_id,
                "user": {
                    "user_id": user_info["user_id"]
                },
                "setup_config": setup_config
            }
            reply_to = "validatorservice.events.create_node"
            await self.__broker_client.publish(routing_key, json.dumps(message), reply_to)
        return success({
            "node": {
                "node_id": node_id,
                "status": NodeStatus.CREATE_RETRYING.name
            }
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
            "node": {
                "node_id": node_id,
                "status": NodeStatus.DELETE_PENDING.name
            }
        })