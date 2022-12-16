import os
import sys
import json
import requests

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiNotFound, ApiForbidden
from database import Database
from utils.broker_client import BrokerClient
from node.status import NodeStatus
from snapshot.status import SnapshotStatus
from utils.helper import convertProtobufToJSON, get_public_ip_droplet
from clouds.providers import default_cloud_provider
from config import VchainApiConfig

current = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(current)))

from validator_share_model.src.messages_queue import node_pb2

_LOGGER = get_logger(__name__)

def convert_node_to_output(
        node, project=None, 
        cloud_provider=default_cloud_provider, 
        syncing=None, can_create_validator=None, 
        validator_info=None, 
        chain_info = None,
        admin_monitoring = None,
    ):
    fullnode_info = node.get("fullnode_info")
    fullnode_address = None
    fullnode_public_key = None
    if fullnode_info and fullnode_info.get("ValidatorInfo"):
        fullnode_address = fullnode_info.get("ValidatorInfo", {}).get("Address")
        fullnode_public_key = fullnode_info.get("ValidatorInfo", {}).get("PubKey", {}).get("value")
    if fullnode_info and fullnode_info.get("validator_info"):
        fullnode_address = fullnode_info.get("validator_info", {}).get("address")
        fullnode_public_key = fullnode_info.get("validator_info", {}).get("pub_key", {}).get("value")
    output = {
        "project_id": node.get("project_id"),
        "node_id": node["node_id"],
        "network": node["network"],
        "moniker": node["moniker"],
        "status": node["status"],
        "message": node.get("message"),
        "created_at": node.get("create_processed_at"),
        "address": fullnode_address,
        "public_key": fullnode_public_key,
        "validator": node.get("validator")
    }
    if project:
        output["project"] = project
    if cloud_provider:
        output["cloud_provider"] = cloud_provider
    if syncing is not None:
        output["syncing"] = syncing
    if can_create_validator is not None: 
        output["can_create_validator"] = can_create_validator
    if validator_info:
        output["validator_info"] = validator_info
    if chain_info:
        output["chain_info"] = chain_info
    if admin_monitoring:
        output["admin_monitoring"] = admin_monitoring
    return output

async def get_syncing_status(droplet_ip):
    try:
        response_status = requests.get(f"http://{droplet_ip}:1317/syncing")
        response_status.raise_for_status()
        data = response_status.json()
        return data["syncing"]
    except Exception as error:
        _LOGGER.error(error)
        return None

async def get_validator_info(droplet_ip, validator_address):
    try:
        response_status = requests.get(f"http://{droplet_ip}:1317/cosmos/staking/v1beta1/validators/{validator_address}")
        response_status.raise_for_status()
        data = response_status.json()
        return data["validator"]
    except Exception as error:
        _LOGGER.error(error)
        return None

async def get_chain_info(network):
    try:
        params = { "chainId": network }
        response_status = requests.get(f"{VchainApiConfig.VCHAIN_API}/api/v1/chain/chain-info", params)
        response_status.raise_for_status()
        data = response_status.json()
        return data["chainInfo"]
    except Exception as error:
        _LOGGER.error(error)
        return None

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
            admin_monitoring = None
            if (node["status"] == NodeStatus.CREATED.name):
                droplet_ip = get_public_ip_droplet(node["droplet"])
                if user_info["role"] == "admin":
                    admin_monitoring = {
                        "ip": droplet_ip,
                        "monitoring_url": f"http://{droplet_ip}:9999/d/cosmos_validator/cosmos-validator"
                    }
            nodes_output.append(convert_node_to_output(node, admin_monitoring=admin_monitoring))
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
        project = None
        if node.get("project_id"):
            project = await self.__database.find_by_id(collection=Database.PROJECTS, id=node.get("project_id"))
        syncing = None
        can_create_validator = False
        admin_monitoring = None
        if (node["status"] == NodeStatus.CREATED.name):
            droplet_ip = get_public_ip_droplet(node["droplet"])
            syncing = await get_syncing_status(droplet_ip)
            can_create_validator = not syncing
            if user_info["role"] == "admin":
                admin_monitoring = {
                    "ip": droplet_ip,
                    "monitoring_url": f"http://{droplet_ip}:9999/d/cosmos_validator/cosmos-validator"
                }
        validator_info = None
        if node.get('validator'):
            validator_address = node['validator'].get('validator_address')
            validator_info = await self.__database.find_one(collection=Database.VALIDATORS, query={"operatorAddress": validator_address})
            if validator_info.get('votingPower') and validator_info.get('totalBondedToken'): 
                validator_info['votingPercentage'] = (100 * validator_info.get('votingPower')) / validator_info.get('totalBondedToken')
            properties_percentage = ['commissionRate', 'commissionMaxRate', 'apr', 'actualStakingAPR', 'finalStakingAPR']
            for item in properties_percentage:
                if validator_info.get(item):
                    validator_info[item] = validator_info.get(item) * 100
            can_create_validator = False
        chain_info = await get_chain_info(node.get("network"))
        return success({
            "node": convert_node_to_output(
                node, project=project, 
                syncing=syncing, 
                can_create_validator=can_create_validator, 
                validator_info=validator_info, 
                chain_info=chain_info,
                admin_monitoring=admin_monitoring
            )
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
        message.setup_config.bond_denom = setup_config["bond_denom"]
        message.setup_config.prefix = setup_config["prefix"]
        message.setup_config.env.node_moniker = setup_config["env"]["node_moniker"]
        message.setup_config.env.volume_name = setup_config["env"]["volume_name"]
        message.setup_config.monitoring_env.telegram_admin = setup_config["monitoring_env"]["telegram_admin"]
        message.setup_config.monitoring_env.telegram_token = setup_config["monitoring_env"]["telegram_token"]
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
        await self.__database.increase_total_nodes_project(project_id=node["project_id"], number=1)

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

        setup_config = await self.__database.find_setup_configs_by_network(network=existed_node["network"])
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

    async def add_validator(self, node_id, validator, user_info):
        existed_node = await self.__database.find_by_id(collection=Database.NODES, id=node_id)
        if existed_node is None:
            raise ApiBadRequest("Node is not found")
        if user_info["role"] != "admin" and user_info["user_id"] != existed_node["user_id"]:
            raise ApiForbidden("")
        if existed_node["status"] != NodeStatus.CREATED.name:
            raise ApiBadRequest("Node not created")
        fullnode_info = existed_node.get("fullnode_info")
        if not fullnode_info:
            raise ApiBadRequest("Fullnode not created")

        modification = { "validator": validator }
        await self.__database.update(collection=Database.NODES, id=node_id, modification=modification)
        await self.__database.create(collection=Database.VALIDATORS, new_document={
            "network": existed_node["network"],
            "moniker": existed_node["moniker"],
            "operatorAddress": validator["validator_address"],
            "publicKey": fullnode_info.get("ValidatorInfo", {}).get("PubKey", {}).get("value"),
        })
        routing_key = "driver.node.request.add_validator_monitoring"
        message = {
            "node_id": node_id,
            "validator": {
                "validator_address": validator["validator_address"],
                "wallet_address": validator["wallet_address"],
                "node_ip": get_public_ip_droplet(existed_node["droplet"])
            }
        }
        reply_to = "validatorservice.events.add_validator_monitoring"
        await self.__broker_client.publish(routing_key, json.dumps(message), reply_to)
        return success({
            "node": {
                "node_id": node_id,
                "validator": validator
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