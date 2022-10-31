import os
import json

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiInternalError

_LOGGER = get_logger(__name__)

class SnapshotHandler:
    def __init__(self, database, broker_client):
        self.__database = database
        self.__broker_client = broker_client

    # async def get_snapshots(self):
        