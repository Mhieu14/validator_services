from json.decoder import JSONDecodeError
from utils.logging import get_logger
from snapshot.routes_handler import SnapshotHandler
from utils.response import success, ApiBadRequest

_LOGGER = get_logger(__name__)

class RouteHandler:
    def __init__(self, database, broker_client):
        self._snapshot_handler = SnapshotHandler(database, broker_client)

    async def get_snapshots(self, request, user_info):
        response = await self._snapshot_handler.get_snapshots()
        return response

    async def get_snapshot(self, request, user_info):
        snapshot_id = request.match_info.get("snapshot_id", "")
        _LOGGER.debug(f"Get snapshot {snapshot_id} information")
        response = await self._snapshot_handler.get_snapshot(snapshot_id=snapshot_id)
        return response

    async def create_snapshot(self, request, user_info):
        _LOGGER.info("Create a new snapshot")
        body = await decode_request(request)
        required_fields = []
        validate_fields(required_fields, body)
        response = await self._snapshot_handler.create_snapshot(new_snapshot=body, user_info=user_info)
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