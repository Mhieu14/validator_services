import asyncio
import json
import croniter

from datetime import datetime
from bson.objectid import ObjectId
from database import Database
from utils.logging import get_logger
from utils.broker_client import BrokerClient
from snapshot.status import SnapshotUpdateStatus, SnapshotStatus
from utils.helper import get_current_timestamp

_LOGGER = get_logger(__name__)

DELAY_UPDATE_SNAPSHOTS = 60 * 60
# DELAY_UPDATE_SNAPSHOTS = 60

async def send_request_update_snapshot(snapshot, setup_config, broker_client):
    routing_key = "driver.snapshot.request.update_snapshot"
    snapshot_id = snapshot["snapshot_id"]
    volume_cloud_id = snapshot["volume_cloud_id"]
    network = snapshot["network"]
    message = {
        "snapshot_id": snapshot_id,
        "snapshot": {
            "volume_cloud_id": volume_cloud_id,
            "network": network
        },
        "setup_config": {
            "network": setup_config["network"],
            "container_name": setup_config["container_name"]
        }
    }
    messageJson = json.dumps(message)
    reply_to = "validatorservice.events.update_snapshot"
    await broker_client.publish(routing_key, messageJson, reply_to)

def get_update_list(snapshots):
    update_snapshot_ids = []
    update_snapshots = []
    for snapshot in snapshots:
        if snapshot.get("cron_time"):
            try:
                current_time = get_current_timestamp()
                cron = croniter.croniter(snapshot["cron_time"], current_time)
                next_time = int(cron.get_next())
            except:
                _LOGGER.error(f"Cron time systax error: {snapshot['snapshot_id']} -> {snapshot['cron_time']}")
                continue
            if current_time + DELAY_UPDATE_SNAPSHOTS > next_time:
                update_snapshot_ids.append(ObjectId(snapshot["snapshot_id"]))
                update_snapshots.append(snapshot)
    return [update_snapshot_ids, update_snapshots]


async def update_snapshots(database: Database, broker_client: BrokerClient):
    # get all snapshot valid for update
    query = {   
        "status": SnapshotStatus.CREATED.name,
        "update_status": {"$ne": SnapshotUpdateStatus.UPDATE_PENDING.name}
    }
    snapshots = await database.find(collection=Database.SNAPSHOTS, query=query)

    # get_update_list
    [update_snapshot_ids, update_snapshots] = get_update_list(snapshots)
    _LOGGER.debug(f"update_snapshot_ids: {update_snapshot_ids}")

    # change status database
    update_query = { "_id": { "$in": update_snapshot_ids }}
    modification = { "update_status": SnapshotUpdateStatus.UPDATE_PENDING.name }
    await database.update_many(collection=Database.SNAPSHOTS, query=update_query, modification=modification)
    
    # push message update
    for snapshot in update_snapshots:
        setup_config = await database.find_setup_configs_by_network(network=snapshot["network"])
        await send_request_update_snapshot(snapshot, setup_config, broker_client)

async def schedule_job(async_func, kwargs, delay):
    while True:
        start_time = get_current_timestamp()
        _LOGGER.debug(f"Cron job processing: {async_func.__name__}")
        try:
            await async_func(**kwargs)
            _LOGGER.debug(f"Cron job success: {async_func.__name__}")
        except Exception as error:
            _LOGGER.error(f"Cron job error: {async_func.__name__} - {error}")
        finish_time = get_current_timestamp()
        sleep_time = delay - (finish_time - start_time)
        if (sleep_time > 0):
            await asyncio.sleep(sleep_time)
            
class CronJob:
    def __init__(self):
        self.database = Database()
        self.broker_client = BrokerClient()

    async def setup(self, loop):
        await self.database.connect()
        loop.create_task(schedule_job(
            async_func=update_snapshots,
            kwargs={
                "database": self.database,
                "broker_client": self.broker_client
            },
            delay=DELAY_UPDATE_SNAPSHOTS
        ))

    async def close_connection(self):
        await self.broker_client.close()

cron = CronJob()
loop = asyncio.get_event_loop()
loop.run_until_complete(cron.setup(loop))
try:
    loop.run_forever()
finally:
    loop.run_until_complete(cron.close_connection())
    _LOGGER.debug("Cron stopped")

loop.close()
