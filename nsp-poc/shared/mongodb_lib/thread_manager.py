"""
스레드 관리 클래스 (리팩토링됨)
"""
from bson.objectid import ObjectId
import logging

from .base_client import BaseMongoClient
from .utils import log_call
from .models import ThreadData

logger = logging.getLogger(__name__)


class ThreadManager(BaseMongoClient):
    """스레드 관리 클래스"""
    
    def __init__(self, mongo_uri: str):
        # [Refactor] mongo_uri를 직접 받아서 부모 클래스에 전달
        super().__init__(mongo_uri)
    
    @log_call
    def add_user_thread(self, org_code: str, user_id: str, function_name: str):
        """사용자-함수 페어에 새로운 스레드를 생성하고 매핑합니다."""
        thread_id = "thread_" + str(ObjectId())
        
        user_thread_collection = self.get_collection(org_code, "user_thread")
        
        # 사용자 스레드 매핑 업데이트
        user_thread_collection.update_one(
            {"user_id": user_id},
            {
                "$setOnInsert": {
                    "user_id": user_id,
                    "threads": []
                }
            },
            upsert=True
        )
        
        result = user_thread_collection.update_one(
            {"user_id": user_id, "threads.function_name": function_name},
            {"$push": {"threads.$.thread": thread_id}}
        )

        if result.matched_count == 0:
            user_thread_collection.update_one(
                {"user_id": user_id},
                {
                    "$push": {
                        "threads": {
                            "function_name": function_name,
                            "thread": [thread_id]
                        }
                    }
                }
            )

        # 스레드 생성
        thread_collection = self.get_collection(org_code, "threads")
        thread_obj = ThreadData(
            _id=thread_id,
            user_id=user_id,
            title=None,
            function_name=function_name
        )
        thread_collection.insert_one(thread_obj.to_dict())
        logger.info(f"Added thread {thread_id} for user {user_id}, function {function_name}")
        return thread_id
    
    @log_call
    def remove_user_thread(self, org_code: str, user_id: str, function_name: str, thread_id: str):
        """사용자-함수 페어에 매핑된 특정 스레드를 제거합니다."""
        user_thread_collection = self.get_collection(org_code, "user_thread")
        
        # 스레드 매핑에서 제거
        user_thread_collection.update_one(
            {"user_id": user_id, "threads.function_name": function_name},
            {"$pull": {"threads.$.thread": thread_id}}
        )
        
        # 빈 스레드 배열 정리
        user_thread_collection.update_one(
            {"user_id": user_id},
            {"$pull": {"threads": {"function_name": function_name, "thread": []}}}
        )
        
        # 스레드 삭제
        thread_collection = self.get_collection(org_code, "threads")
        thread_collection.delete_one({"_id": thread_id})
        
        logger.info(f"Removed thread {thread_id} for user {user_id}, function {function_name}")
    
    @log_call
    def get_user_threads(self, org_code: str, user_id: str, function_name: str):
        """특정 사용자와 함수에 매핑된 스레드 ID 리스트를 반환합니다."""
        user_thread_collection = self.get_collection(org_code, "user_thread")
        entry = user_thread_collection.find_one({"user_id": user_id})
        if not entry:
            return []
        
        for func in entry.get("threads", []):
            if func.get("function_name") == function_name:
                return func.get("thread", [])
        return []
    
    @log_call
    def check_user_thread(self, org_code: str, user_id: str, function_name: str, thread_id: str):
        """특정 사용자와 함수에 매핑된 스레드의 존재 여부를 확인합니다."""
        threads = self.get_user_threads(org_code, user_id, function_name)
        return thread_id in threads
    
    @log_call
    def get_thread(self, org_code: str, thread_id: str):
        """스레드 정보를 조회합니다."""
        thread_collection = self.get_collection(org_code, "threads")
        return thread_collection.find_one({"_id": thread_id})
    
    @log_call
    def update_thread_title(self, org_code: str, thread_id: str, title: str):
        """스레드 제목을 업데이트합니다."""
        thread_collection = self.get_collection(org_code, "threads")
        result = thread_collection.update_one(
            {"_id": thread_id},
            {"$set": {"title": title}}
        )
        return result.modified_count > 0
    
    @log_call
    def check_thread_title(self, org_code: str, thread_id: str):
        """스레드에 저장된 제목이 있는지 확인하고 반환합니다."""
        thread = self.get_thread(org_code, thread_id)
        if not thread:
            return None
        
        title = thread.get("title")
        return title if title and title.strip() else None