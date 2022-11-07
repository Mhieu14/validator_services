import json

from utils.logging import get_logger
from database import Database
from snapshot.status import SnapshotStatus
from utils.broker_client import BrokerClient

_LOGGER = get_logger(__name__)

async def handle_create_snapshot_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about snapshot creating process")
    try:
        snapshot_id = body["snapshot_id"]
        if 'error' in body:
            modification = {
                "status": SnapshotStatus.CREATE_FAIL.name,
                "message": body["error"]["message"],
                "detail": body["error"]["detail"]
            }
            await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
        else:
            snapshot = await database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
            if (snapshot["status"] in [SnapshotStatus.CREATE_PENDING.name, SnapshotStatus.CREATE_FAIL.name]):
                modification = {
                    "snapshot_cloud_id": body["data"]["id"],
                    "status": SnapshotStatus.CREATED.name
                }
                await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
    except:
        _LOGGER.debug(f"Exec handle_create_snapshot_event fail message_id: {message_id}")

async def handle_delete_snapshot_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about snapshot deleting process")
    try:
        snapshot_id = body["snapshot_id"]
        if 'error' in body:
            modification = {
                "status": SnapshotStatus.DELETE_FAIL.name,
                "message": body["error"]["message"],
                "detail": body["error"]["detail"]
            }
            await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
        else:
            snapshot = await database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
            if (snapshot["status"] in [SnapshotStatus.DELETE_PENDING.name, SnapshotStatus.DELETE_FAIL.name]):
                modification = {
                    "status": SnapshotStatus.DELETED.name
                }
                await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
    except:
        _LOGGER.debug(f"Exec handle_delete_snapshot_event fail message_id: {message_id}")

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
