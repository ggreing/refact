from pymongo import MongoClient
from .config import MongoConfig


class BaseMongoClient:
    """MongoDB 클라이언트의 기본 클래스"""
    
    def __init__(self, config: MongoConfig = None):
        self.config = config or MongoConfig()
        self.client = MongoClient(self.config.mongo_uri)
    
    def get_database(self, db_name: str):
        """특정 데이터베이스를 반환합니다."""
        return self.client[db_name]
    
    def get_collection(self, db_name: str, collection_name: str):
        """특정 컬렉션을 반환합니다."""
        return self.client[db_name][collection_name]
    
    def close(self):
        """MongoDB 연결을 닫습니다."""
        if self.client:
            self.client.close()