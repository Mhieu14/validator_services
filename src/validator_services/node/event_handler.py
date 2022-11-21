import json
from datetime import datetime, timezone

from utils.logging import get_logger
from database import Database
from node.status import NodeStatus
from utils.broker_client import BrokerClient
from utils.helper import get_current_isodate

_LOGGER = get_logger(__name__)

async def handle_create_node_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about node creating node")
    try:
        node_id = body["node_id"]
        volume = body["volume"]
        droplet = body["droplet"]
        fullnode_info = body["fullnode_info"]
        process = body["process"]
        modification = {
            "volume": volume,
            "droplet": droplet,
            "fullnode_info": fullnode_info,
            "create_process": process,
            "create_processed_at": datetime.now(tz=timezone.utc)
        }
        if 'error' in body:
            modification["status"] = NodeStatus.CREATE_FAIL.name
            modification["message"] = body["error"]["message"]
            modification["detail"] = body["error"]["detail"]
        else:
            modification["status"] = NodeStatus.CREATED.name
        _LOGGER.debug("Done")
        await database.update(collection=Database.NODES, id=node_id, modification=modification)
    except:
        _LOGGER.error(f"Exec handle_delete_node_event fail message_id: {message_id}")


async def handle_delete_node_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about node deleting node")
    try:
        node_id = body["node_id"]
        if 'error' in body:
            modification = {
                "status": NodeStatus.DELETE_FAIL.name,
                "message": body["error"]["message"],
                "detail": body["error"]["detail"],
                "delete_processed_at": datetime.now(tz=timezone.utc)
            }
            await database.update(collection=Database.NODES, id=node_id, modification=modification)
        else:
            node = await database.find_by_id(collection=Database.NODES, id=node_id)
            if (node["status"] in [NodeStatus.DELETE_PENDING.name, NodeStatus.DELETE_FAIL.name]):
                modification = {
                    "status": NodeStatus.DELETED.name,
                    "delete_processed_at": datetime.now(tz=timezone.utc)
                }
                await database.update(collection=Database.NODES, id=node_id, modification=modification)
    except:
        _LOGGER.error(f"Exec handle_delete_node_event fail message_id: {message_id}")
    
async def test_handle_request_create_node(body, reply_to, message_id, database: Database):
    try:
        print("test_handle_request_create_node")
        broker_client = BrokerClient()
        routing_key = reply_to
        message = {
            "node_id": body["node_id"],
            "error": {
                "message": "A random error"
            },
            "data": {
                "id": "nodesnapshot_cloud_id_123",
                "name": "name"
            }
        }
        await broker_client.publish_dict_data(routing_key, message)
    except:
        _LOGGER.debug("Exec test_handle_request_create_node fail message_id: ", message_id)