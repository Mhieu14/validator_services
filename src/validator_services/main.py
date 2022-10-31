import sys
import asyncio
import aiohttp_cors

from aiohttp import web, ClientSession
from config import Config
from utils.logging import get_logger
from database import Database
from routes_handler import RouteHandler
from utils.broker_client import BrokerClient
from utils.middleware import self_authorize

from snapshot.event_handler import handle_create_snapshot_event

_LOGGER = get_logger(__name__)

app = web.Application(middlewares=[self_authorize], client_max_size=1024 ** 2)

async def setup_service(app):
    try:
        database = Database()
        await database.connect()

        app["broker_client"] = BrokerClient()
        
        event_handlers = {
            "edit_name_of_topic": handle_create_snapshot_event
        }

        asyncio.create_task(app["broker_client"].consume("validatorservice.events", event_handlers, database))

        handler = RouteHandler(database, app["broker_client"])

        app.router.add_route("GET", "/v1/snapshots", handler.get_snapshots)
        app.router.add_route("POST", "/v1/snapshots", handler.create_snapshot)

        cors = aiohttp_cors.setup(
            app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*"
                )
            },
        )
        for route in list(app.router.routes()):
            cors.add(route)

    except Exception as error:
        _LOGGER.error(error)
        sys.exit(1)

async def cleanup_resources(app):
    await app["broker_client"].close()


app.on_startup.append(setup_service)
app.on_cleanup.append(cleanup_resources)

web.run_app(app)
