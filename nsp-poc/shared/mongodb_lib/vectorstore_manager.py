"""
벡터스토어 관리 클래스 (리팩토링됨)
"""
from typing import List, Optional, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from .base_client import BaseMongoClient
from .utils import log_call

logger = logging.getLogger(__name__)


class VectorstoreManager(BaseMongoClient):
    """벡터스토어 관리 클래스"""
    
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
    def add_vectorstore(self, org_code: str, vector_id: str, files: Optional[List[dict]] = None):
        """벡터스토어 항목을 추가하거나 업데이트합니다."""
        collection = self.get_collection(org_code, "vectorstore")
        files = files or []
        
        try:
            result = collection.update_one(
                {"_id": vector_id},
                {
                    "$setOnInsert": {
                        "_id": vector_id,
                        "created_at": self.current_time
                    },
                    "$push": {"files": {"$each": files}},
                    "$set": {"updated_at": self.current_time}
                },
                upsert=True
            )
            
            if result.upserted_id is not None:
                logger.info(f"Vectorstore entry created: {vector_id}")
            elif files:
                logger.info(f"Vectorstore entry updated with new files: {vector_id}")
            else:
                logger.info(f"No files provided to add for: {vector_id}")
            
            return True
        except Exception as e:
            logger.error(f"Failed to add/update vectorstore entry: {vector_id}", exc_info=True)
            raise
    
    @log_call
    def get_vectorstore_entry(self, org_code: str, vector_id: str):
        """벡터스토어에서 지정된 벡터 ID에 해당하는 문서를 조회합니다."""
        collection = self.get_collection(org_code, "vectorstore")
        entry = collection.find_one({"_id": vector_id})
        
        if entry:
            logger.debug(f"Vectorstore entry found: {vector_id}")
            return entry
        else:
            logger.info(f"No vectorstore entry found with id: {vector_id}")
            return None
    
    @log_call
    def delete_vectorstore_entry(self, org_code: str, vector_id: str):
        """벡터스토어에서 지정된 벡터 ID에 해당하는 문서를 삭제합니다."""
        collection = self.get_collection(org_code, "vectorstore")
        result = collection.delete_one({"_id": vector_id})
        
        if result.deleted_count > 0:
            logger.info(f"Vectorstore entry deleted: {vector_id}")
            return True
        else:
            logger.warning(f"No vectorstore entry found with id: {vector_id} to delete.")
            return False
    
    @log_call
    def get_thread_vectorstore(self, org_code: str, thread_id: str) -> Optional[Any]:
        """주어진 스레드의 vectorestore 값을 조회합니다."""
        collection = self.get_collection(org_code, "threads")
        thread = collection.find_one({"_id": thread_id})
        
        if not thread:
            logger.warning(f"Thread {thread_id} not found in {org_code} DB")
            return None

        return thread.get("vectorestore")
    
    @log_call
    def set_thread_vectorstore(self, org_code: str, thread_id: str, vectorestore_value: Any) -> bool:
        """주어진 스레드의 vectorestore 값을 덮어씁니다."""
        collection = self.get_collection(org_code, "threads")
        result = collection.update_one(
            {"_id": thread_id},
            {
                "$set": {
                    "vectorestore": vectorestore_value,
                    "last_timestamp": self.current_time
                }
            }
        )
        
        if result.matched_count > 0:
            logger.info(f"Vectorestore updated for thread {thread_id}")
            return True
        else:
            logger.warning(f"Thread {thread_id} not found, cannot set vectorstore.")
            return False
    
    @log_call
    def list_vectorstore_entries(self, org_code: str, limit: int = None):
        """벡터스토어의 모든 엔트리 목록을 조회합니다."""
        collection = self.get_collection(org_code, "vectorstore")
        cursor = collection.find({})
        if limit:
            cursor = cursor.limit(limit)
        return list(cursor)
    
    @log_call
    def update_vectorstore_metadata(self, org_code: str, vector_id: str, metadata: dict):
        """벡터스토어 항목의 메타데이터를 업데이트합니다."""
        collection = self.get_collection(org_code, "vectorstore")
        metadata['updated_at'] = self.current_time
        result = collection.update_one(
            {"_id": vector_id},
            {"$set": {"metadata": metadata}}
        )
        if result.modified_count > 0:
            logger.info(f"Vectorstore metadata updated for {vector_id}")
        return result.modified_count > 0