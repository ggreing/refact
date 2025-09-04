from .base_client import BaseMongoClient
from .utils import log_call


class UserManager(BaseMongoClient):
    """사용자 관리 클래스"""
    
    def __init__(self, config=None):
        super().__init__(config)
    
    @log_call
    def create_user(self, og_code: str, name: str, user_id: str):
        """사용자 정보를 MongoDB에 저장합니다."""
        collection = self.get_collection(og_code, "user")
        
        user_data = {
            "_id": user_id,
            "name": name,
            "created_at": self.config.current_time
        }
        try:
            collection.insert_one(user_data)
            print(f"User created: {name} ({user_id})")
            return True
        except Exception as e:
            print(f"Failed to create user: {name} ({user_id})")
            raise
    
    @log_call
    def get_user(self, og_code: str, user_id: str):
        """사용자 고유 ID로 MongoDB의 사용자 문서를 조회합니다."""
        collection = self.get_collection(og_code, "user")
        user = collection.find_one({"_id": user_id})
        if user:
            print(f"User found: {user['name']} ({user['_id']})")
            return user
        else:
            print(f"No user found with user_id: {user_id}")
            return None
    
    @log_call
    def update_user(self, og_code: str, user_id: str, update_data: dict):
        """사용자 정보를 업데이트합니다."""
        collection = self.get_collection(og_code, "user")
        update_data['updated_at'] = self.config.current_time
        result = collection.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    @log_call
    def delete_user(self, og_code: str, user_id: str):
        """사용자 고유 ID로 MongoDB의 사용자 문서를 삭제합니다."""
        collection = self.get_collection(og_code, "user")
        result = collection.delete_one({"_id": user_id})
        if result.deleted_count > 0:
            print(f"User with user_id {user_id} deleted.")
            return True
        else:
            print(f"No user found with user_id {user_id}.")
            return False
    
    @log_call
    def list_users(self, og_code: str, limit: int = None):
        """기관의 모든 사용자 목록을 조회합니다."""
        collection = self.get_collection(og_code, "user")
        cursor = collection.find({})
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)