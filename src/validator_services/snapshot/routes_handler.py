import os
import sys

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiForbidden, ApiNotFound
from database import Database
from utils.broker_client import BrokerClient
from snapshot.status import SnapshotStatus
from utils.helper import convertProtobufToJSON

current = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.dirname(os.path.dirname(current)))

from validator_share_model.src.messages_queue import snapshot_pb2

_LOGGER = get_logger(__name__)

class SnapshotHandler:
    def __init__(self, database: Database, broker_client: BrokerClient):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client

    async def get_snapshots(self, user_info, skip, limit):
        # query = { "user_id": user_info["user_id"] }
        query = {}
        snapshots = await self.__database.find(collection=Database.SNAPSHOTS, query=query, skip=skip, limit=limit)
        count_snapshots = await self.__database.count(collection=Database.SNAPSHOTS, query=query)
        return success({
            "snapshots": snapshots,
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
        return success(snapshot)
    
    async def create_snapshot(self, snapshot, user_info):
        snapshot["user_id"] = user_info["user_id"]
        snapshot["user_create_role"] = user_info["role"]
        snapshot["status"] = SnapshotStatus.CREATE_PENDING.name
        created_id = await self.__database.create(collection=Database.SNAPSHOTS, new_document=snapshot)
        routing_key = "driver.snapshot.request.create"

        message = snapshot_pb2.SnapshotCreateMessage()
        message.snapshot_id = created_id
        message.snapshot.name = snapshot["name"]
        message.snapshot.volumn_cloud_id = snapshot["volumn_cloud_id"]
        message.snapshot.tags.extend(snapshot.get("tags", []))
        message.snapshot.network = snapshot["network"]
        message.snapshot.droplet_cloud_id = snapshot["droplet_cloud_id"]
        messageJson = convertProtobufToJSON(message)

        reply_to = "validatorservice.events.create_snapshot"
        await self.__broker_client.publish(routing_key, messageJson, reply_to)
        return success({
            "snapshot_id": created_id,
            "status": SnapshotStatus.CREATE_PENDING.name
        })
    
    async def delete_snapshot(self, snapshot_id, user_info):
        existed_snapshot = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        if existed_snapshot is None:
            raise ApiBadRequest("Snapshot is not found")
        if user_info["role"] != "admin" and user_info["user_id"] != existed_snapshot["user_id"]:
            raise ApiForbidden("")
        if existed_snapshot["status"] in [SnapshotStatus.DELETE_PENDING.name, SnapshotStatus.DELETED.name]:
            return success({
                "snapshot_id": snapshot_id,
                "status": existed_snapshot["status"]
            })
        
        modification = { "status": SnapshotStatus.DELETE_PENDING.name}
        await self.__database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)

        routing_key = "driver.snapshot.request.delete"
        message = snapshot_pb2.SnapshotDeleteMessage()
        message.snapshot_id = snapshot_id
        messageJson = convertProtobufToJSON(message)
        
        reply_to = "validatorservice.events.delete_snapshot"
        await self.__broker_client.publish(routing_key, messageJson, reply_to)

        return success({
            "snapshot_id": snapshot_id,
            "status": SnapshotStatus.DELETE_PENDING.name
        })