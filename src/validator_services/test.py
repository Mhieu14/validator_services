import sys
import os
current = os.path.dirname(os.path.realpath(__file__))
parent = os.path.dirname(current)
sys.path.append(parent)

from validator_share_model.src.messages_queue import snapshot_pb2
from google.protobuf.json_format import MessageToJson
import json

def convertProtobufToDict(protobufData): 
    return json.loads(MessageToJson(message=protobufData, preserving_proto_field_name=True))

snapshotCreateMessage = snapshot_pb2.SnapshotCreateMessage()
snapshotCreateMessage.snapshot_id = "1"
snapshotCreateMessageData = snapshot_pb2.SnapshotCreateMessage.Snapshot()
print(type(snapshotCreateMessageData))
snapshotCreateMessageData.name = "1"
print(snapshotCreateMessageData)
snapshotCreateMessage.snapshot.name = "snapshotCreateMessageData"

print(MessageToJson(snapshotCreateMessage))
jsonSnapshotCreateMessage = convertProtobufToDict(snapshotCreateMessage)
print(jsonSnapshotCreateMessage)
print(jsonSnapshotCreateMessage["snapshot_id"])
print(type(jsonSnapshotCreateMessage))
print(jsonSnapshotCreateMessage)

