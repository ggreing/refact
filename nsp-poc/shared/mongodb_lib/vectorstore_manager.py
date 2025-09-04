from typing import List, Optional, Any
from .base_client import BaseMongoClient
from .utils import log_call


class VectorstoreManager(BaseMongoClient):
    """벡터스토어 관리 클래스"""
    
    def __init__(self, config=None):
        super().__init__(config)
    
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
                        "created_at": self.config.current_time
                    },
                    "$push": {"files": {"$each": files}},
                    "$set": {"updated_at": self.config.current_time}
                },
                upsert=True
            )
            
            if result.upserted_id is not None:
                print(f"Vectorstore entry created: {vector_id}")
            elif files:
                print(f"Vectorstore entry updated with new files: {vector_id}")
            else:
                print(f"No files provided to add for: {vector_id}")
            
            return True
        except Exception as e:
            print(f"Failed to add/update vectorstore entry: {vector_id}")
            raise
    
    @log_call
    def get_vectorstore_entry(self, org_code: str, vector_id: str):
        """벡터스토어에서 지정된 벡터 ID에 해당하는 문서를 조회합니다."""
        collection = self.get_collection(org_code, "vectorstore")
        entry = collection.find_one({"_id": vector_id})
        
        if entry:
            print(f"Vectorstore entry found: {vector_id}")
            return entry
        else:
            print(f"No vectorstore entry found with id: {vector_id}")
            return None
    
    @log_call
    def delete_vectorstore_entry(self, org_code: str, vector_id: str):
        """벡터스토어에서 지정된 벡터 ID에 해당하는 문서를 삭제합니다."""
        collection = self.get_collection(org_code, "vectorstore")
        result = collection.delete_one({"_id": vector_id})
        
        if result.deleted_count > 0:
            print(f"Vectorstore entry deleted: {vector_id}")
            return True
        else:
            print(f"No vectorstore entry found with id: {vector_id}")
            return False
    
    @log_call
    def get_thread_vectorstore(self, org_code: str, thread_id: str) -> Optional[Any]:
        """주어진 스레드의 vectorestore 값을 조회합니다."""
        collection = self.get_collection(org_code, "threads")
        thread = collection.find_one({"_id": thread_id})
        
        if not thread:
            print(f"Thread {thread_id} not found in {org_code} DB")
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
                    "last_timestamp": self.config.current_time
                }
            }
        )
        
        if result.matched_count > 0:
            print(f"Vectorestore updated for thread {thread_id}")
            return True
        else:
            print(f"Thread {thread_id} not found")
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
        metadata['updated_at'] = self.config.current_time
        result = collection.update_one(
            {"_id": vector_id},
            {"$set": {"metadata": metadata}}
        )
        return result.modified_count > 0