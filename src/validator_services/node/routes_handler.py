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
from node.validator_info import get_validator_info_rest_api

current = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(current)))

from validator_share_model.src.messages_queue import node_pb2

_LOGGER = get_logger(__name__)
NODE_PROMEHEUS_PORT = 9092
NODE_REST_PORT = 1317
NODE_RPC_PORT = 26657
NODE_GRAFANA_PORT = 9999
NODE_PROTOCOL = "http"

def convert_node_to_output(
        node, project=None, 
        cloud_provider=default_cloud_provider, 
        syncing=None, can_create_validator=None, 
        validator_info=None, 
        chain_info = None,
        admin_monitoring = None,
        chain_stake_info = None,
        monitoring = None,
        sync_info = None,
        endpoint = None,
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
    if chain_stake_info:
        output["chain_stake_info"] = chain_stake_info
    if monitoring:
        output["monitoring"] = monitoring
    if sync_info:
        output["sync_info"] = sync_info
    if endpoint:
        output["endpoint"] = endpoint
    return output

async def get_syncing_status(droplet_ip):
    try:
        response_status = requests.get(f"{NODE_PROTOCOL}://{droplet_ip}:1317/syncing")
        response_status.raise_for_status()
        data = response_status.json()
        return data["syncing"]
    except Exception as error:
        _LOGGER.error(error)
        return None

async def get_node_status_rpc(droplet_ip):
    try:
        response_status = requests.get(f"{NODE_PROTOCOL}://{droplet_ip}:26657/status")
        response_status.raise_for_status()
        data = response_status.json()
        return data["result"]
    except Exception as error:
        _LOGGER.error(error)
        return {}

# async def get_validator_info(droplet_ip, validator_address):
#     try:
#         response_status = requests.get(f"http://{droplet_ip}:1317/cosmos/staking/v1beta1/validators/{validator_address}")
#         response_status.raise_for_status()
#         data = response_status.json()
#         return data["validator"]
#     except Exception as error:
#         _LOGGER.error(error)
#         return None

def get_admin_monitoring(droplet_ip):
    return {
        "ip": droplet_ip,
        "monitoring_url": f"{NODE_PROTOCOL}://{droplet_ip}:{NODE_GRAFANA_PORT}/d/cosmos_validator/cosmos-validator"
    }

async def get_chain_info(network):
    try:
        params = { "network": network }
        response_status = requests.get(f"{VchainApiConfig.VCHAIN_API}/api/v1/staking/chain-stake-info", params)
        response_status.raise_for_status()
        data = response_status.json()
        tokens_bonded = data.get("stakeInfo").get("totalBondedToken")
        tokens_not_bonded = data.get("stakeInfo").get("totalNotBondedTokens")
        tokens_total = None
        if (tokens_not_bonded is not None and tokens_bonded is not None):
            tokens_total = tokens_bonded + tokens_not_bonded 
        chain_stake_info = {
            "name" : data.get("chainInfo").get("chainName"),
            "price": data.get("stakeInfo").get("price"),
            "tokens_bonded": data.get("stakeInfo").get("totalBondedToken"),
            "tokens_total": tokens_total,
            "apr": data.get("stakeInfo").get("apr") * 100,
            "decimal": data.get("chainInfo").get("decimal")
        }
        return {
            "chain_info": data.get("chainInfo"),
            "chain_stake_info": chain_stake_info
        }
    except Exception as error:
        _LOGGER.error(f"get_chain_info error: {error}")
        return {
            "chain_info": None,
            "chain_stake_info": None
        }

async def get_validator_info(database: Database, node):
    validator_address = node['validator'].get('validator_address')
    validator_info = await database.find_one(collection=Database.VALIDATORS, query={"operatorAddress": validator_address})
    if validator_info.get('votingPower') and validator_info.get('totalBondedToken'): 
        validator_info['votingPercentage'] = (100 * validator_info.get('votingPower')) / validator_info.get('totalBondedToken')
    properties_percentage = ['commissionRate', 'commissionMaxRate', 'apr', 'actualStakingAPR', 'finalStakingAPR']
    for item in properties_percentage:
        if validator_info.get(item):
            validator_info[item] = validator_info.get(item) * 100
    return validator_info

async def get_node_monitoring_query_range(droplet_ip):
    query = "node_cpu_seconds_total"
    res = requests.get(f"http://{droplet_ip}:{NODE_PROMEHEUS_PORT}/api/v1/query?query={query}[1m]")
    res.raise_for_status()
    res_results = res.json()["data"]["result"]
    cpu_count = 0
    time_start = res_results[0]["values"][0][0]
    time_end = res_results[0]["values"][-1][0]
    deltas = []
    for result in res_results:
        if (result["metric"]["mode"] == "idle"):
            value_start = float(result["values"][0][1])
            value_end = float(result["values"][-1][1])
            deltas.append(value_end - value_start)
            cpu_count = cpu_count + 1
    return {
        "cpu_percentage": round(100 - 100 * sum(deltas) / len(deltas) / (time_end - time_start), 1),
        "cpu_count": cpu_count
    }

async def get_node_monitoring_query_momment(droplet_ip):
    query = "{__name__=~'node_memory_MemTotal_bytes|node_memory_MemAvailable_bytes'}"
    res = requests.get(f"http://{droplet_ip}:{NODE_PROMEHEUS_PORT}/api/v1/query?query={query}")
    res.raise_for_status()
    res_results = res.json()["data"]["result"]

    node_memory_total_bytes = 0
    node_memory_available_bytes = 0
    for result in res_results:
        if (result["metric"]["__name__"] == "node_memory_MemTotal_bytes"):
            node_memory_total_bytes = float(result["value"][1])
        if (result["metric"]["__name__"] == "node_memory_MemAvailable_bytes"):
            node_memory_available_bytes = float(result["value"][1])
    return {
        "ram_total": f"{round(node_memory_total_bytes / 10**9, 2)} GB",
        "ram_used": f"{round((node_memory_total_bytes - node_memory_available_bytes) / 10**9, 2)} GB",
        "ram_percentage": round(100 - 100 * (node_memory_available_bytes / node_memory_total_bytes), 1)
    }
        
async def get_node_monitoring(droplet_ip):
    try:
        query_range = await get_node_monitoring_query_range(droplet_ip)
        query_momment = await get_node_monitoring_query_momment(droplet_ip)
        result = {}
        result.update(query_range)
        result.update(query_momment)
        return result
    except Exception as error:
        _LOGGER.error(f"get_node_basic_monitoring_info error: {error}")
        return {}

def get_node_endpoint(droplet_ip):
    return {
        "lcd": f"{NODE_PROTOCOL}://{droplet_ip}:{NODE_REST_PORT}",
        "rpc": f"{NODE_PROTOCOL}://{droplet_ip}:{NODE_RPC_PORT}",
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
            admin_monitoring = None
            if (node["status"] == NodeStatus.CREATED.name):
                droplet_ip = get_public_ip_droplet(node["droplet"])
                admin_monitoring = get_admin_monitoring(droplet_ip) if user_info["role"] == "admin" else None
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

    async def get_nodes_admin(self, user_info={}, project_id=None, skip=None, limit=None):
        if user_info["role"] != "admin":
            raise ApiForbidden("")
        nodes_data = await self.get_nodes_data({}, project_id, skip, limit)
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

        chain = await get_chain_info(node.get("network"))

        if (node["status"] != NodeStatus.CREATED.name):
            return success({
                "node": convert_node_to_output(
                    node, project=project, 
                    syncing=False,
                    can_create_validator=False,
                    chain_info=chain["chain_info"],
                    chain_stake_info=chain["chain_stake_info"]
                )
            })

        droplet_ip = get_public_ip_droplet(node["droplet"])
        node_status = await get_node_status_rpc(droplet_ip)
        sync_info = node_status.get("sync_info", {})
        syncing = sync_info.get("catching_up")
        admin_monitoring = get_admin_monitoring(droplet_ip) if user_info["role"] == "admin" else None
        endpoint = get_node_endpoint(droplet_ip)
        monitoring = await get_node_monitoring(droplet_ip)
        validator_info = await get_validator_info_rest_api(node, chain["chain_info"], chain["chain_stake_info"]) if node.get('validator') else None
        print(validator_info)
        can_create_validator = (not node.get('validator')) and syncing == False
        return success({
            "node": convert_node_to_output(
                node, project=project, 
                syncing=syncing, 
                can_create_validator=can_create_validator, 
                validator_info=validator_info,
                chain_info=chain["chain_info"],
                chain_stake_info=chain["chain_stake_info"],
                admin_monitoring=admin_monitoring,
                sync_info=sync_info,
                monitoring=monitoring,
                endpoint=endpoint
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
            "publicKey": fullnode_info.get("validator_info", {}).get("pub_key", {}).get("value"),
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