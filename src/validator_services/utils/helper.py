from google.protobuf.json_format import MessageToJson, MessageToDict
import json
from datetime import datetime

def convertProtobufToJSON(protobufData): 
    return MessageToJson(message=protobufData, preserving_proto_field_name=True)

def convertProtobufToDict(protobufData): 
    return json.loads(convertProtobufToJSON(protobufData))

def get_current_isodate():
    current_date = datetime.now()
    return current_date.isoformat()