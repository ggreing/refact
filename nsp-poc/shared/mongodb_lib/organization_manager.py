from .base_client import BaseMongoClient
from .utils import log_call


class OrganizationManager(BaseMongoClient):
    """기관(Organization) 관리 클래스"""
    
    def __init__(self, config=None):
        super().__init__(config)
        self.og_keys_collection = self.get_collection("og_keys", "og_keys")
    
    @log_call
    def create_og_entry(self, og_name: str, og_code: str, og_key: str):
        """새로운 기관 엔트리를 생성합니다."""
        og_data = {
            "name": og_name,
            "code": og_code,
            "key": og_key,
            "created_at": self.config.current_time,
            "updated_at": self.config.current_time
        }
        try:
            self.og_keys_collection.insert_one(og_data)
            print(f"OG entry created: {og_code}")
        except Exception as e:
            print(f"Failed to create OG entry: {og_code}")
            raise
    
    @log_call
    def update_og_key(self, og_code: str, new_key: str):
        """기존 기관의 액세스 키를 갱신합니다."""
        result = self.og_keys_collection.update_one(
            {"code": og_code},
            {
                "$set": {
                    "key": new_key, 
                    "updated_at": self.config.current_time
                }
            }
        )
        if result.matched_count > 0:
            print(f"OG key updated for code {og_code}")
        else:
            print(f"No OG entry found with code: {og_code}")
        return result.modified_count > 0
    
    @log_call
    def get_og_entry(self, og_code: str):
        """기관 코드에 해당하는 기관 엔트리를 조회합니다."""
        og_entry = self.og_keys_collection.find_one({"code": og_code})
        if og_entry:
            print(f"OG entry found: {og_code}")
            return og_entry
        else:
            print(f"No OG entry found with code: {og_code}")
            return None
    
    @log_call
    def verify_og_key(self, og_code: str, og_key: str):
        """전달된 액세스 키가 저장된 키와 일치하는지 검증합니다."""
        og_entry = self.og_keys_collection.find_one({"code": og_code})
        if og_entry and og_entry.get("key") == og_key:
            print(f"OG key verified for code {og_code}")
            return True
        else:
            print(f"OG key verification failed for code {og_code}")
            return False
    
    @log_call
    def delete_og_entry(self, og_code: str):
        """기관 엔트리를 삭제합니다."""
        result = self.og_keys_collection.delete_one({"code": og_code})
        return result.deleted_count > 0