from google.protobuf.json_format import MessageToJson, MessageToDict
import json

def convertProtobufToJSON(protobufData): 
    return MessageToJson(message=protobufData, preserving_proto_field_name=True)

def convertProtobufToDict(protobufData): 
    return json.loads(convertProtobufToJSON(protobufData))
