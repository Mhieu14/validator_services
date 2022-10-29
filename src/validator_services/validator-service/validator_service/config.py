import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    RUN_SETTINGS = {
        'host': os.environ.get('SERVER_HOST', 'localhost'),
        'port': int(os.environ.get('SERVER_PORT', 8080))
    }

class DBConfig:
    DATABASE = os.environ.get("MONGO_DATABASE") or "validator-service"
    USERNAME = os.environ.get("MONGO_USERNAME") or "vchain"
    PASSWORD = os.environ.get("MONGO_PASSWORD") or "vchain123"
    HOST = os.environ.get("MONGO_HOST") or "localhost"
    PORT = os.environ.get("MONGO_PORT") or "27017"

class QueueConfig:
    USERNAME = os.environ.get("RABBITMQ_USERNAME") or "guest"
    PASSWORD = os.environ.get("RABBITMQ_PASSWORD") or "guest"
    HOST = os.environ.get("RABBITMQ_HOST") or "localhost"
    PORT = os.environ.get("RABBITMQ_PORT") or "5672"