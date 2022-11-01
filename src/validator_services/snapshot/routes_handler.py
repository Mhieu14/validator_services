import os
import json

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiInternalError
from database import Database
from utils.broker_client import BrokerClient
from snapshot.status import SnapshotStatus

_LOGGER = get_logger(__name__)

class SnapshotHandler:
    def __init__(self, database: Database, broker_client: BrokerClient):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client

    async def get_snapshots(self, user_info):
        query = { "user_id": user_info["user_id"] }
        snapshots = await self.__database.find(collection=Database.SNAPSHOTS, query=query)
        return success(snapshots)

    async def get_snapshot(self, snapshot_id):
        snapshot = await self.__database.find_by_id(collection=Database.SNAPSHOTS, id=snapshot_id)
        return success(snapshot)
    
    async def create_snapshot(self, snapshot, user_info):
        snapshot["user_id"] = user_info["user_id"]
        snapshot["status"] = SnapshotStatus.CREATE_PENDING.name
        created_id = await self.__database.create(collection=Database.SNAPSHOTS, new_document=snapshot)
        routing_key = "driver.snapshot.request.create"
        message = {
            "snapshot_id": created_id,
            "data": {
                "name": snapshot["name"],
                "node_cloud_id": snapshot.get("node_cloud_id", None),
                "update_frequence": snapshot.get("update_frequence", None),
            }
        }
        json_message = json.dumps(message)
        reply_to = "validatorservice.events.create_snapshot"
        await self.__broker_client.publish(routing_key, json_message, reply_to)
        return success({
            "id": created_id,
            "status": SnapshotStatus.CREATE_PENDING.name
        })
    
    async def delete_snapshot(self, snapshot_id):
        modification = { "status": SnapshotStatus.DELETE_PENDING.name}
        await self.__database.update(collection=Database.SNAPSHOTS, id=snapshot_id, modification=modification)

        routing_key = "driver.snapshot.request.delete"
        message = { "snapshot_id": snapshot_id }
        json_message = json.dumps(message)
        reply_to = "validatorservice.events.delete_snapshot"
        await self.__broker_client.publish(routing_key, json_message, reply_to)

        return success({
            "id": snapshot_id,
            "status": SnapshotStatus.DELETE_PENDING.name
        })