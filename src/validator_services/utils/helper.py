from google.protobuf.json_format import MessageToJson, MessageToDict
import json
from datetime import datetime, timezone

def convertProtobufToJSON(protobufData): 
    return MessageToJson(message=protobufData, preserving_proto_field_name=True)

def convertProtobufToDict(protobufData): 
    return json.loads(convertProtobufToJSON(protobufData))

def get_current_isodate():
    current_date = datetime.now(tz=timezone.utc)
    return current_date.isoformat()

def get_current_timestamp():
    return int(datetime.timestamp(datetime.now(tz=timezone.utc)))