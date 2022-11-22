import sys
import asyncio
import aiohttp_cors
import sys
import os

from aiohttp import web, ClientSession
from aiohttp_swagger import setup_swagger
from config import Config
from utils.logging import get_logger
from database import Database
from routes_handler import RouteHandler
from utils.broker_client import BrokerClient
from utils.middleware import self_authorize

from snapshot.event_handler import handle_create_snapshot_event, handle_delete_snapshot_event, handle_update_snapshot_event
from node.event_handler import handle_create_node_event, handle_delete_node_event

current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

_LOGGER = get_logger(__name__)

app = web.Application(middlewares=[self_authorize], client_max_size=1024 ** 2)

async def setup_service(app):
    try:
        database = Database()
        await database.connect()

        app["broker_client"] = BrokerClient()
        
        event_handlers = {
            "validatorservice.events.create_snapshot": handle_create_snapshot_event,
            "validatorservice.events.delete_snapshot": handle_delete_snapshot_event,
            "validatorservice.events.update_snapshot": handle_update_snapshot_event,
            "validatorservice.events.create_node": handle_create_node_event,
            "validatorservice.events.delete_node": handle_delete_node_event,
        }

        # event_handlers_test = {
        #     "driver.snapshot.request.create": test_handle_request_create_snapshot,
        #     "driver.node.request.create": test_handle_request_create_node
        # }

        asyncio.create_task(app["broker_client"].consume("validatorservice.events", event_handlers, database))
        # asyncio.create_task(app["broker_client"].consume("test.driver.request", event_handlers_test, database))

        handler = RouteHandler(database, app["broker_client"])

        # project
        app.router.add_route("GET", "/v1/projects", handler.get_projects)
        app.router.add_route("GET", "/v1/projects/{project_id}", handler.get_project)
        app.router.add_route("POST", "/v1/projects", handler.create_project)
        app.router.add_route("DELETE", "/v1/projects/{project_id}", handler.delete_project)

        # snapshot
        app.router.add_route("GET", "/v1/snapshots", handler.get_snapshots)
        app.router.add_route("GET", "/v1/snapshots/{snapshot_id}", handler.get_snapshot)
        app.router.add_route("POST", "/v1/snapshots", handler.create_snapshot)
        app.router.add_route("PUT", "/v1/snapshots/{snapshot_id}", handler.update_info_snapshot)
        app.router.add_route("DELETE", "/v1/snapshots/{snapshot_id}", handler.delete_snapshot)
        app.router.add_route("POST", "/v1/snapshots/{snapshot_id}/update", handler.update_snapshot)

        # node
        app.router.add_route("GET", "/v1/nodes", handler.get_nodes)
        app.router.add_route("GET", "/v1/nodes/{node_id}", handler.get_node)
        app.router.add_route("POST", "/v1/nodes", handler.create_node)
        app.router.add_route("POST", "/v1/nodes/{node_id}/retry", handler.retry_create_node)
        app.router.add_route("DELETE", "/v1/nodes/{node_id}", handler.delete_node)
        
        # network
        app.router.add_route("GET", "/v1/networks", handler.get_networks)

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

setup_swagger(app, swagger_url="/v1/doc", swagger_from_file="swagger.yaml")

web.run_app(app)
