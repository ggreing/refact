"""
MongoDB 클라이언트의 기본 클래스 (리팩토링됨)
"""
from pymongo import MongoClient
# [Refactor] MongoConfig 의존성 제거

class BaseMongoClient:
    """MongoDB 클라이언트의 기본 클래스"""
    
    def __init__(self, mongo_uri: str):
        # [Refactor] MongoConfig 대신 mongo_uri 문자열을 직접 받음
        if not mongo_uri:
            raise ValueError("mongo_uri must be provided")
        self.mongo_uri = mongo_uri
        self.client = MongoClient(self.mongo_uri)
    
    def get_database(self, db_name: str):
        """특정 데이터베이스를 반환합니다."""
        return self.client[db_name]
    
    def get_collection(self, db_name: str, collection_name: str):
        """특정 컬렉션을 반환합니다."""
        # [Refactor] db_name을 settings에서 가져오도록 수정할 수 있으나,
        # 일단은 유연성을 위해 파라미터로 유지.
        # 중앙 설정의 db_name을 사용하려면 self.client[settings.mongodb_database]...
        return self.client[db_name][collection_name]
    
    def close(self):
        """MongoDB 연결을 닫습니다."""
        if self.client:
            self.client.close()