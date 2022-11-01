from json.decoder import JSONDecodeError
from urllib import response
from utils.logging import get_logger
from snapshot.routes_handler import SnapshotHandler
from utils.response import ApiBadRequest
from project.routes_handler import ProjectHandler

_LOGGER = get_logger(__name__)

class RouteHandler:
    def __init__(self, database, broker_client):
        self._snapshot_handler = SnapshotHandler(database, broker_client)
        self._project_handler = ProjectHandler(database, broker_client)

    # projects
    async def create_project(self, request, user_info):
        project = await decode_request(request)
        required_fields = ["name"]
        validate_fields(required_fields, project)
        response = await self._project_handler.create_project(project, user_info)
        return response

    async def get_projects(self, request, user_info):
        user_id = user_info["user_id"]
        response = await self._project_handler.get_projects(user_id)
        return response

    # snapshots
    async def create_snapshot(seft, request, user_info):
        _LOGGER.info("Create a new snapshot")
        snapshot = await decode_request(request)
        required_fields = ["node_id", "name"]
        validate_fields(required_fields, snapshot)
        response = await seft._snapshot_handler.create_snapshot(snapshot, user_info)
        return response

    async def delete_snapshot(seft, request, user_info):
        _LOGGER.info("Delete a snapshot")
        body = await decode_request(request)
        required_fields = ["snapshot_id"]
        validate_fields(required_fields, body)
        response = await seft._snapshot_handler.delete_snapshot(body["snapshot_id"])
        return response

    async def get_snapshots(self, request, user_info):
        response = await self._snapshot_handler.get_snapshots(user_info)
        return response

    async def get_snapshot(self, request, user_info):
        snapshot_id = request.match_info.get("snapshot_id", "")
        _LOGGER.debug(f"Get snapshot {snapshot_id} information")
        response = await self._snapshot_handler.get_snapshot(snapshot_id=snapshot_id)
        return response

async def decode_request(request):
    try:
        return await request.json()
    except JSONDecodeError:
        raise ApiBadRequest('Improper JSON format')


def validate_fields(required_fields, body):
    for field in required_fields:
        if body.get(field) is None:
            raise ApiBadRequest(f"'{field}' parameter is required")