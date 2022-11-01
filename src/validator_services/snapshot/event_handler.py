import json

from utils.logging import get_logger
from database import Database
from snapshot.status import SnapshotStatus
from utils.broker_client import BrokerClient

_LOGGER = get_logger(__name__)

async def handle_create_snapshot_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about snapshot creating process")
    if "snapshot_id" not in body:
        return
    snapshot_id = body["snapshot_id"]
    if 'error' in body:
        modification = {
            "status": SnapshotStatus.CREATE_FAIL.name,
            "message": body["error"]["message"]
        }
        await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
    else:
        snapshot = await database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        if (snapshot["status"] in [SnapshotStatus.CREATE_PENDING.name, SnapshotStatus.CREATE_FAIL.name]):
            modification = {
                "status": SnapshotStatus.CREATED.name
            }
            await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)

async def handle_delete_snapshot_event(body, reply_to, message_id, database: Database):
    # Handle event response from driver
    _LOGGER.debug("Receiving response about snapshot deleting process")
    if "snapshot_id" not in body:
        return
    snapshot_id = body["snapshot_id"]
    if 'error' in body:
        modification = {
            "status": SnapshotStatus.DELETE_FAIL.name,
            "message": body["error"]["message"]
        }
        await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)
    else:
        snapshot = await database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        if (snapshot["status"] in [SnapshotStatus.DELETE_PENDING.name, SnapshotStatus.DELETE_FAIL.name]):
            modification = {
                "status": SnapshotStatus.DELETED.name
            }
            await database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)

    
async def test_handle_request_create_snapshot(body, reply_to, message_id, database: Database):
    print("HERRRRRRRRRRRRRRRRRRE")
    broker_client = BrokerClient()
    routing_key = reply_to
    message = {
        "snapshot_id": body["snapshot_id"],
        "error": {
            "message": "A random error" 
        },
        "data": {
            "name": "name"
        }
    }
    json_message = json.dumps(message)
    await broker_client.publish(routing_key, json_message)