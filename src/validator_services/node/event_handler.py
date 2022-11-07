import json

from utils.logging import get_logger
from database import Database
from node.status import NodeStatus
from utils.broker_client import BrokerClient
from utils.helper import get_current_isodate
from snapshot.status import SnapshotStatus

_LOGGER = get_logger(__name__)

async def handle_create_node_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about node creating process")
    print("===================", body)
    node_id = body["node_id"]
    if 'error' in body:
        modification = {
            "status": SnapshotStatus.CREATE_FAIL.name,
            "message": body["error"]["message"],
            "detail": body["error"]["detail"],
            "create_processed_at": get_current_isodate()
        }
        await database.update(collection=Database.NODES, id=node_id, modification=modification)
    else:
        node = await database.find_by_id(collection=Database.NODES, id=node_id)
        if (node["status"] in [SnapshotStatus.CREATE_PENDING.name, SnapshotStatus.CREATE_FAIL.name]):
            modification = {
                "volumn_cloud_id": body["snapshot"]["id"],
                "name": body["snapshot"]["name"],
                "regions": body["snapshot"]["regions"],
                "resource_id": body["snapshot"]["resource_id"],
                "resource_type": body["snapshot"]["resource_type"],
                "size_gigabytes": body["snapshot"]["size_gigabytes"],
                "status": SnapshotStatus.CREATED.name,
                "create_processed_at": get_current_isodate()
            }
            await database.update(collection=Database.NODES, id=node_id, modification=modification)

async def handle_delete_node_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about node deleting process")
    try:
        node_id = body["node_id"]
        if 'error' in body:
            modification = {
                "status": NodeStatus.DELETE_FAIL.name,
                "message": body["error"]["message"],
                "detail": body["error"]["detail"],
                "delete_processed_at": get_current_isodate()
            }
            await database.update(collection=Database.NODES, id=node_id, modification=modification)
        else:
            node = await database.find_by_id(collection=Database.NODES, id=node_id)
            if (node["status"] in [NodeStatus.DELETE_PENDING.name, NodeStatus.DELETE_FAIL.name]):
                modification = {
                    "status": NodeStatus.DELETED.name,
                    "delete_processed_at": get_current_isodate()
                }
                await database.update(collection=Database.NODES, id=node_id, modification=modification)
    except:
        _LOGGER.debug(f"Exec handle_delete_node_event fail message_id: {message_id}")
    
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