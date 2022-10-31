import json

from utils.logging import get_logger

_LOGGER = get_logger(__name__)

async def handle_create_snapshot_event(body, reply_to, message_id, database):
    _LOGGER.debug("Receiving response about snapshot creating process")

    # Handle event response from driver