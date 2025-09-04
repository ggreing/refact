"""
사용자 관리 클래스 (리팩토링됨)
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from .base_client import BaseMongoClient
from .utils import log_call

logger = logging.getLogger(__name__)


class UserManager(BaseMongoClient):
    """사용자 관리 클래스"""
    
    def __init__(self, mongo_uri: str):
        # [Refactor] mongo_uri를 직접 받아서 부모 클래스에 전달
        super().__init__(mongo_uri)
        # [Refactor] 시간대 정보를 자체적으로 관리
        self.KST = ZoneInfo("Asia/Seoul")

    @property
    def current_time(self) -> datetime:
        # [Refactor] config 객체 대신 자체적으로 현재 시간 반환
        return datetime.now(self.KST)

    @log_call
    def create_user(self, og_code: str, name: str, user_id: str):
        """사용자 정보를 MongoDB에 저장합니다."""
        collection = self.get_collection(og_code, "user")
        
        user_data = {
            "_id": user_id,
            "name": name,
            "created_at": self.current_time
        }
        try:
            collection.insert_one(user_data)
            logger.info(f"User created: {name} ({user_id})")
            return True
        except Exception as e:
            logger.error(f"Failed to create user: {name} ({user_id})", exc_info=True)
            raise
    
    @log_call
    def get_user(self, og_code: str, user_id: str):
        """사용자 고유 ID로 MongoDB의 사용자 문서를 조회합니다."""
        collection = self.get_collection(og_code, "user")
        user = collection.find_one({"_id": user_id})
        if user:
            logger.debug(f"User found: {user['name']} ({user['_id']})")
            return user
        else:
            logger.info(f"No user found with user_id: {user_id}")
            return None
    
    @log_call
    def update_user(self, og_code: str, user_id: str, update_data: dict):
        """사용자 정보를 업데이트합니다."""
        collection = self.get_collection(og_code, "user")
        update_data['updated_at'] = self.current_time
        result = collection.update_one(
            {"_id": user_id},
            {"$set": update_data}
        )
        if result.modified_count > 0:
            logger.info(f"User {user_id} updated.")
        return result.modified_count > 0
    
    @log_call
    def delete_user(self, og_code: str, user_id: str):
        """사용자 고유 ID로 MongoDB의 사용자 문서를 삭제합니다."""
        collection = self.get_collection(og_code, "user")
        result = collection.delete_one({"_id": user_id})
        if result.deleted_count > 0:
            logger.info(f"User with user_id {user_id} deleted.")
            return True
        else:
            logger.warning(f"No user found with user_id {user_id} to delete.")
            return False
    
    @log_call
    def list_users(self, og_code: str, limit: int = None):
        """기관의 모든 사용자 목록을 조회합니다."""
        collection = self.get_collection(og_code, "user")
        cursor = collection.find({})
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)