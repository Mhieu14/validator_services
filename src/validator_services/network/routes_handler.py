import os
import json

from aiohttp import web
from utils.logging import get_logger
from utils.response import success, ApiBadRequest, ApiNotFound, ApiForbidden
from database import Database
from utils.broker_client import BrokerClient

_LOGGER = get_logger(__name__)

class NetworkHandler:
    def __init__(self, database, broker_client):
        self.__database: Database = database
        self.__broker_client: BrokerClient = broker_client

    async def get_networks(self):
        networks = await self.__database.find_all_network()
        result = []
        for network in networks:
            result.append({
                "network": network["network"],
                "name": network["name"]
            })
        return success({
            "networks": result
        })