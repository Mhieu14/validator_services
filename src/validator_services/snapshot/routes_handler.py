import os
import sys
import json
import croniter

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiForbidden, ApiNotFound
from database import Database
from utils.broker_client import BrokerClient
from snapshot.status import SnapshotStatus, SnapshotUpdateStatus
from utils.helper import convertProtobufToJSON

current = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(current)))

from validator_share_model.src.messages_queue import snapshot_pb2

_LOGGER = get_logger(__name__)

def convert_snapshot_to_output(snapshot):
    return {
        "name": snapshot["name"],
        "snapshot_id": snapshot["snapshot_id"],
        "network": snapshot["network"],
        "status": snapshot["status"],
        "message": snapshot.get("message"),
        "detail": snapshot.get("detail"),
        "created_at": snapshot.get("create_processed_at"),
        "update_status": snapshot.get("update_status"),
        "update_message": snapshot.get("update_message"),
        "update_detail": snapshot.get("update_detail"),
        "updated_at": snapshot.get("update_processed_at"),
        "snapshot_cloud_id": snapshot.get("snapshot_cloud_id"),
        "volume_cloud_id": snapshot.get("volume_cloud_id"),
        "droplet_cloud_id": snapshot.get("droplet_cloud_id"),
        "snapshot_cloud_created_at": snapshot.get("snapshot_cloud", {}).get("created_at")
    }

class SnapshotHandler:
    def __init__(self, database: Database, broker_client: BrokerClient):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client

    async def get_snapshots(self, user_info, skip, limit):
        # query = { "user_id": user_info["user_id"] }
        query = {   
            "status": {"$ne": SnapshotStatus.DELETED.name}
        }
        snapshots = await self.__database.find(collection=Database.SNAPSHOTS, query=query, skip=skip, limit=limit)
        count_snapshots = await self.__database.count(collection=Database.SNAPSHOTS, query=query)
        snapshots_output = []
        for snapshot in snapshots:
            snapshots_output.append(convert_snapshot_to_output(snapshot))
        return success({
            "snapshots": snapshots_output,
            "meta": {
                "offset": skip,
                "limit": limit,
                "total": count_snapshots
            }
        })

    async def get_snapshot(self, snapshot_id):
        snapshot = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        if snapshot is None:
            return ApiNotFound("Snapshot")
        return success({
            "snapshot": convert_snapshot_to_output(snapshot)
        })
    
    async def create_snapshot(self, snapshot, user_info):
        if user_info["role"] != "admin":
            raise ApiForbidden("")

        snapshot["user_id"] = user_info["user_id"]
        snapshot["user_create_role"] = user_info["role"]
        snapshot["status"] = SnapshotStatus.CREATE_PENDING.name
        created_id = await self.__database.create(collection=Database.SNAPSHOTS, new_document=snapshot)
        
        routing_key = "driver.snapshot.request.create_snapshot"
        message = snapshot_pb2.SnapshotCreateMessage()
        message.snapshot_id = created_id
        message.snapshot.name = snapshot["name"]
        message.snapshot.volume_cloud_id = snapshot["volume_cloud_id"]
        message.snapshot.tags.extend(snapshot.get("tags", []))
        message.snapshot.network = snapshot["network"]
        message.user.user_id = user_info["user_id"]
        messageJson = convertProtobufToJSON(message)

        reply_to = "validatorservice.events.create_snapshot"
        await self.__broker_client.publish(routing_key, messageJson, reply_to)
        return success({
            "snapshot": {
                "snapshot_id": created_id,
                "status": SnapshotStatus.CREATE_PENDING.name
            }
        })

    async def update_info_snapshot(self, snapshot_id, snapshot, user_info):
        existed_snapshot = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        if existed_snapshot is None:
            raise ApiBadRequest("Snapshot is not found")
        if user_info["role"] != "admin" and user_info["user_id"] != existed_snapshot["user_id"]:
            raise ApiForbidden("")
        
        modification = {}
        if snapshot.get("name"):
            modification["name"] = snapshot.get("name")
        if snapshot.get("cron_time"):
            try:
                croniter.croniter(snapshot.get("cron_time"))
            except Exception as error:
                raise ApiBadRequest(f"cron_time: {error}")
            modification["cron_time"] = snapshot.get("cron_time")
        if snapshot.get("volume_cloud_id"):
            modification["volume_cloud_id"] = snapshot.get("volume_cloud_id")
        updated_snapshot = await self.__database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)

        return success({
            "snapshot": convert_snapshot_to_output(updated_snapshot)
        })
    
    async def delete_snapshot(self, snapshot_id, user_info):
        existed_snapshot = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        if existed_snapshot is None:
            raise ApiBadRequest("Snapshot is not found")
        if user_info["role"] != "admin" and user_info["user_id"] != existed_snapshot["user_id"]:
            raise ApiForbidden("")
        if existed_snapshot["status"] in [SnapshotStatus.DELETE_PENDING.name, SnapshotStatus.DELETED.name]:
            raise ApiBadRequest("Snapshot is deleted or deleting")
        if existed_snapshot["status"] == SnapshotStatus.CREATE_PENDING.name:
            raise ApiBadRequest("Snapshot is creating")
        if "update_status" in existed_snapshot and existed_snapshot["update_status"] == SnapshotUpdateStatus.UPDATE_PENDING.name:
            raise ApiBadRequest("Snapshot is updating")
        
        modification = { "status": SnapshotStatus.DELETE_PENDING.name}
        await self.__database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)

        routing_key = "driver.snapshot.request.delete_snapshot"
        message = snapshot_pb2.SnapshotDeleteMessage()
        message.snapshot_id = snapshot_id
        messageJson = convertProtobufToJSON(message)
        
        reply_to = "validatorservice.events.delete_snapshot"
        await self.__broker_client.publish(routing_key, messageJson, reply_to)

        return success({
            "snapshot": {
                "snapshot_id": snapshot_id,
                "status": SnapshotStatus.DELETE_PENDING.name
            }
        })

    async def update_snapshot(self, snapshot_id, user_info):
        existed_snapshot = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        if existed_snapshot is None:
            raise ApiBadRequest("Snapshot is not found")
        if user_info["role"] != "admin" and user_info["user_id"] != existed_snapshot["user_id"]:
            raise ApiForbidden("")
        if existed_snapshot["status"] != SnapshotStatus.CREATED.name:
            raise ApiBadRequest("Snapshot is not created")
        if existed_snapshot.get("update_status") == SnapshotUpdateStatus.UPDATE_PENDING.name:
            raise ApiBadRequest("Snapshot is updating")

        modification = {
            "update_status": SnapshotUpdateStatus.UPDATE_PENDING.name 
        }
        await self.__database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)

        routing_key = "driver.snapshot.request.update_snapshot"
        volume_cloud_id = existed_snapshot["volume_cloud_id"]
        network = existed_snapshot["network"]
        message = {
            "snapshot_id": snapshot_id,
            "snapshot": {
                "volume_cloud_id": volume_cloud_id,
                "network": network
            }
        }
        messageJson = json.dumps(message)
        reply_to = "validatorservice.events.update_snapshot"
        await self.__broker_client.publish(routing_key, messageJson, reply_to)

        return success({
            "snapshot": {
                "snapshot_id": snapshot_id,
                "update_status": SnapshotUpdateStatus.UPDATE_PENDING.name
            }
        })