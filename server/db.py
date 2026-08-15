from pymongo import MongoClient
from config import Config

# Module-level singleton instance for the entire project
mongo_client = MongoClient(Config.MONGODB_URI, serverSelectionTimeoutMS=2000)

def get_db():
    return mongo_client[Config.MONGODB_DB_NAME]
