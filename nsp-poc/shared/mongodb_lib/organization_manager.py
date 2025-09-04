"""
기관(Organization) 관리 클래스 (리팩토링됨)
"""
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from .base_client import BaseMongoClient
from .utils import log_call

logger = logging.getLogger(__name__)


class OrganizationManager(BaseMongoClient):
    """기관(Organization) 관리 클래스"""
    
    def __init__(self, mongo_uri: str):
        # [Refactor] mongo_uri를 직접 받아서 부모 클래스에 전달
        super().__init__(mongo_uri)
        # [Refactor] 시간대 정보를 자체적으로 관리
        self.KST = ZoneInfo("Asia/Seoul")
        self.og_keys_collection = self.get_collection("og_keys", "og_keys")

    @property
    def current_time(self) -> datetime:
        # [Refactor] config 객체 대신 자체적으로 현재 시간 반환
        return datetime.now(self.KST)

    @log_call
    def create_og_entry(self, og_name: str, og_code: str, og_key: str):
        """새로운 기관 엔트리를 생성합니다."""
        og_data = {
            "name": og_name,
            "code": og_code,
            "key": og_key,
            "created_at": self.current_time,
            "updated_at": self.current_time
        }
        try:
            self.og_keys_collection.insert_one(og_data)
            logger.info(f"OG entry created: {og_code}")
        except Exception as e:
            logger.error(f"Failed to create OG entry: {og_code}", exc_info=True)
            raise
    
    @log_call
    def update_og_key(self, og_code: str, new_key: str):
        """기존 기관의 액세스 키를 갱신합니다."""
        result = self.og_keys_collection.update_one(
            {"code": og_code},
            {
                "$set": {
                    "key": new_key, 
                    "updated_at": self.current_time
                }
            }
        )
        if result.matched_count > 0:
            logger.info(f"OG key updated for code {og_code}")
        else:
            logger.warning(f"No OG entry found with code: {og_code} to update key.")
        return result.modified_count > 0
    
    @log_call
    def get_og_entry(self, og_code: str):
        """기관 코드에 해당하는 기관 엔트리를 조회합니다."""
        og_entry = self.og_keys_collection.find_one({"code": og_code})
        if og_entry:
            logger.debug(f"OG entry found: {og_code}")
            return og_entry
        else:
            logger.info(f"No OG entry found with code: {og_code}")
            return None
    
    @log_call
    def verify_og_key(self, og_code: str, og_key: str):
        """전달된 액세스 키가 저장된 키와 일치하는지 검증합니다."""
        og_entry = self.og_keys_collection.find_one({"code": og_code})
        if og_entry and og_entry.get("key") == og_key:
            logger.info(f"OG key verified for code {og_code}")
            return True
        else:
            logger.warning(f"OG key verification failed for code {og_code}")
            return False
    
    @log_call
    def delete_og_entry(self, og_code: str):
        """기관 엔트리를 삭제합니다."""
        result = self.og_keys_collection.delete_one({"code": og_code})
        if result.deleted_count > 0:
            logger.info(f"Deleted OG entry for code: {og_code}")
        return result.deleted_count > 0