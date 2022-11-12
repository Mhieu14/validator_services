from json.decoder import JSONDecodeError
from urllib import response
from utils.logging import get_logger
from snapshot.routes_handler import SnapshotHandler
from utils.response import success, ApiBadRequest
from project.routes_handler import ProjectHandler
from node.routes_handler import NodeHandler
from clouds.droplet_sizes import droplet_sizes_available

_LOGGER = get_logger(__name__)

class RouteHandler:
    def __init__(self, database, broker_client):
        self._snapshot_handler = SnapshotHandler(database, broker_client)
        self._project_handler = ProjectHandler(database, broker_client)
        self._node_handler = NodeHandler(database, broker_client)

    # projects
    async def create_project(self, request, user_info):
        _LOGGER.debug("Create a new project")
        project = await decode_request(request)
        required_fields = ["name"]
        validate_fields(required_fields, project)
        response = await self._project_handler.create_project(project, user_info)
        return response

    async def get_projects(self, request, user_info):
        _LOGGER.debug(f"Get all networks of the user: {user_info['user_id']}")
        skip = int(request.rel_url.query.get("offset", 0))
        limit = int(request.rel_url.query.get("limit", 20))
        response = await self._project_handler.get_projects(user_info, skip, limit)
        return response

    async def get_project(self, request, user_info):
        project_id = request.match_info.get("project_id", "")
        # body = await decode_request(request)
        skip = int(request.rel_url.query.get("offset", 0))
        limit = int(request.rel_url.query.get("limit", 20))
        print(skip, limit)
        _LOGGER.debug(f"Get project {project_id} information")
        response = await self._project_handler.get_project(project_id, skip, limit)
        return response

    # snapshots
    async def create_snapshot(seft, request, user_info):
        _LOGGER.debug("Create a new snapshot")
        snapshot = await decode_request(request)
        required_fields = ["volumn_cloud_id", "name", "network", "droplet_cloud_id"]
        validate_fields(required_fields, snapshot)
        response = await seft._snapshot_handler.create_snapshot(snapshot, user_info)
        return response

    async def delete_snapshot(seft, request, user_info):
        _LOGGER.debug("Delete a snapshot")
        snapshot_id = request.match_info.get("snapshot_id", "")
        response = await seft._snapshot_handler.delete_snapshot(snapshot_id, user_info)
        return response

    async def get_snapshots(self, request, user_info):
        skip = int(request.rel_url.query.get("offset", 0))
        limit = int(request.rel_url.query.get("limit", 20))
        _LOGGER.debug(f"Get all snapshot")
        response = await self._snapshot_handler.get_snapshots(user_info, skip, limit)
        return response

    async def get_snapshot(self, request, user_info):
        snapshot_id = request.match_info.get("snapshot_id", "")
        _LOGGER.debug(f"Get snapshot {snapshot_id} information")
        response = await self._snapshot_handler.get_snapshot(snapshot_id=snapshot_id)
        return response

    # nodes
    async def create_node(seft, request, user_info):
        _LOGGER.debug("Create a new node")
        node = await decode_request(request)
        required_fields = ["network", "moniker"]
        node["droplet_size"] = node.get("droplet_size", "s-1vcpu-1gb")
        if (node["droplet_size"] not in droplet_sizes_available):
            raise ApiBadRequest(f"droplet_size invalid")
        validate_fields(required_fields, node)
        response = await seft._node_handler.create_node(node, user_info)
        return response

    async def delete_node(seft, request, user_info):
        node_id = request.match_info.get("node_id", "")
        _LOGGER.debug(f"Delete a node: {node_id}")
        response = await seft._node_handler.delete_node(node_id, user_info)
        return response

    async def get_nodes(self, request, user_info):
        skip = int(request.rel_url.query.get("offset", 0))
        limit = int(request.rel_url.query.get("limit", 20))
        project_id = request.rel_url.query.get("project_id")
        response = await self._node_handler.get_nodes(user_info, project_id, skip, limit)
        return response

    async def get_node(self, request, user_info):
        node_id = request.match_info.get("node_id", "")
        _LOGGER.debug(f"Get node {node_id} information")
        response = await self._node_handler.get_node(node_id=node_id)
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