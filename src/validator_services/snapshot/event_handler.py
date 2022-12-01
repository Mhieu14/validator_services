import json
from datetime import datetime, timezone

from utils.logging import get_logger
from database import Database
from snapshot.status import SnapshotStatus, SnapshotUpdateStatus
from utils.broker_client import BrokerClient
from utils.helper import get_current_isodate

_LOGGER = get_logger(__name__)

async def handle_create_snapshot_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about snapshot creating snapshot")
    try:
        snapshot_id = body["snapshot_id"]
        modification = {
            "create_processed_at": datetime.now(tz=timezone.utc)
        }
        if "error" in body:
            modification["status"] = SnapshotStatus.CREATE_FAIL.name
            modification["message"] = body["error"]["message"]
            modification["detail"] = body["error"]["detail"]
        else:
            modification["snapshot_cloud"] = body["snapshot_cloud"]
            modification["snapshot_cloud_id"] = body["snapshot_cloud"]["snapshot_cloud_id"]
            modification["droplet_cloud_id"] = body["droplet_cloud_id"]
            modification["status"] = SnapshotStatus.CREATED.name
        await database.update(
            collection=Database.SNAPSHOTS,
            id=snapshot_id,
            modification=modification)
        _LOGGER.debug("Done")
    except:
        _LOGGER.debug(f"Exec handle_create_snapshot_event fail message_id: {message_id}")

async def handle_delete_snapshot_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about snapshot deleting snapshot")
    try:
        snapshot_id = body["snapshot_id"]
        if 'error' in body:
            modification = {
                "status": SnapshotStatus.DELETE_FAIL.name,
                "message": body["error"]["message"],
                "detail": body["error"]["detail"],
                "delete_processed_at": datetime.now(tz=timezone.utc)
            }
            await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
        else:
            snapshot = await database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
            if (snapshot["status"] in [SnapshotStatus.DELETE_PENDING.name, SnapshotStatus.DELETE_FAIL.name]):
                modification = {
                    "status": SnapshotStatus.DELETED.name,
                    "delete_processed_at": datetime.now(tz=timezone.utc)
                }
                await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
    except:
        _LOGGER.debug(f"Exec handle_delete_snapshot_event fail message_id: {message_id}")

async def handle_update_snapshot_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about snapshot updating snapshot")
    try:
        snapshot_id = body["snapshot_id"]
        modification = {
            "update_processed_at": datetime.now(tz=timezone.utc)
        }
        if body.get("error"):
            modification["update_status"] = SnapshotUpdateStatus.UPDATE_FAIL.name
            modification["update_message"] = body["error"]["message"]
            modification["update_detail"] = body["error"]["detail"]
        else:
            modification["snapshot_cloud"] = body["snapshot_cloud"]
            modification["snapshot_cloud_id"] = body["snapshot_cloud"]["snapshot_cloud_id"]
            modification["droplet_cloud_id"] = body["droplet_cloud_id"]
            modification["update_status"] = SnapshotUpdateStatus.UPDATED.name
        await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
        if not body.get("error"):
            broker_client = BrokerClient()
            message = { "snapshot_id": snapshot_id }
            await broker_client.publish(message=json.dumps(message), routing_key=reply_to)
    except Exception as error:
        _LOGGER.error(error, exc_info=True)
        _LOGGER.debug(f"Exec handle_update_snapshot_event fail message_id: {message_id}")

async def test_handle_request_create_snapshot(body, reply_to, message_id, database: Database):
    try:
        print("test_handle_request_create_snapshot")

        print(body)
        print(type(body))
        broker_client = BrokerClient()
        routing_key = reply_to
        message = {
            "snapshot_id": body["snapshot_id"],
            # "error": {
            #     "message": "A random error" 
            # },
            "data": {
                "id": "snapshot_cloud_id_123",
                "name": "name"
            }
        }
        await broker_client.publish_dict_data(routing_key, message)
    except:
        _LOGGER.debug("Exec test_handle_request_create_snapshot fail message_id: ", message_id)
