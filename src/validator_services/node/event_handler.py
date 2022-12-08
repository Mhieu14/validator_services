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
        node_id = body.get("node_id")
        volume = body.get("volume")
        droplet = body.get("droplet")
        fullnode_info = body.get("fullnode_info")
        process = body.get("process")
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
    except Exception as error:
        _LOGGER.error(error, exc_info=True)
        _LOGGER.error(f"Exec handle_create_node_event fail: {str(error)}")


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
                await database.increase_total_nodes_project(project_id=node["project_id"], number=-1)
                await database.update(collection=Database.NODES, id=node_id, modification=modification)
    except Exception as error:
        _LOGGER.error(f"Exec handle_delete_node_event fail: {str(error)}")

async def handle_response_add_validator_monitoring(body, reply_to, message_id, database: Database):
    _LOGGER.info(f"Receive a response to add_validator_monitoring from driver")
    try:
        node_id = body["node_id"]
        if 'error' in body:
            modification = {
                "validator_monitoring_status": "FAIL",
                "validator_monitoring_message": body["error"]["message"],
                "validator_monitoring_detail": body["error"]["detail"],
                "validator_monitoring_processed_at": datetime.now(tz=timezone.utc)
            }
            await database.update(collection=Database.NODES, id=node_id, modification=modification)
        else:
            modification = {
                "validator_monitoring_status": "SUCCESS",
                "validator_monitoring_message": None,
                "validator_monitoring_detail": None,
                "validator_monitoring_processed_at": datetime.now(tz=timezone.utc)
            }
            await database.update(collection=Database.NODES, id=node_id, modification=modification)
    except Exception as error:
        _LOGGER.error(f"Exec handle_response_add_validator_monitoring fail: {str(error)}")