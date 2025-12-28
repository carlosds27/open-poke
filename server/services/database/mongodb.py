import certifi
import pymongo
from bson import json_util
from ...config import get_settings


class MongoDB:
    _instance = None

    @classmethod
    def get_instance(cls) -> "MongoDB":
        if cls._instance is None:
            cls._instance = cls.get_new_instance()
        return cls._instance

    @classmethod
    def get_new_instance(cls):
        settings = get_settings()
        client_url = f"mongodb+srv://{settings.mongodb_user}:{settings.mongodb_pass}@{settings.mongodb_uri}.mongodb.net/"
        return cls(client_url=client_url, db_name=settings.mongodb_database)

    def __init__(self, client_url, db_name):
        self.client = pymongo.MongoClient(client_url, tlsCAFile=certifi.where())
        self.db = self.client[db_name]

    def close(self):
        self.client.close()

    # Might want to remove this later since we don't have to define the method
    # since we can just directly call drop_collection and self.db is accessible
    def drop_collection(self, collection_name):
        self.db.drop_collection(collection_name)

    def get_collection_by_name(self, collection_name):
        return self.db[collection_name]

    def get_collection_list(self):
        return self.db.list_collection_names()

    def get_db_name(self):
        return self.db_name

    @classmethod
    def serialize(cls, cursor):
        return json_util.dumps(cls.get_serialize_able(cursor=cursor), indent=4)

    @classmethod
    def get_serialize_able(cls, cursor):
        return [
            {
                column: value
                for column, value in row.items()
                if not column.startswith("_")
            }
            for row in cursor
        ]
