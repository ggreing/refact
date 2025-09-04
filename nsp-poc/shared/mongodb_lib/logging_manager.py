"""
로그 관리 클래스 (리팩토링됨)
"""
from typing import Dict
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import logging

from .base_client import BaseMongoClient
from .utils import log_call

logger = logging.getLogger(__name__)


class LoggingManager(BaseMongoClient):
    """로그 관리 클래스"""
    
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
    def log_error(self, org_code: str, error_data: dict):
        """에러 로그를 저장합니다."""
        collection = self.get_collection(org_code, "error_log")
        error_entry = {
            "error_data": error_data,
            "timestamp": self.current_time
        }
        collection.insert_one(error_entry)
        return True
    
    @log_call
    def get_error_logs(self, org_code: str, limit: int = None):
        """에러 로그를 조회합니다."""
        collection = self.get_collection(org_code, "error_log")
        cursor = collection.find({}).sort("timestamp", -1)
        
        if limit:
            cursor = cursor.limit(limit)
            
        return list(cursor)
    
    @log_call
    def log_user_activity(self, org_code: str, user_id: str, activity: str, details: dict = None):
        """사용자 활동 로그를 저장합니다."""
        collection = self.get_collection(org_code, "activity_log")
        activity_entry = {
            "user_id": user_id,
            "activity": activity,
            "details": details or {},
            "timestamp": self.current_time
        }
        collection.insert_one(activity_entry)
        return True
    
    @log_call
    def get_user_activities(self, org_code: str, user_id: str = None, activity: str = None, limit: int = None):
        """사용자 활동 로그를 조회합니다."""
        collection = self.get_collection(org_code, "activity_log")
        query = {}
        
        if user_id:
            query["user_id"] = user_id
        if activity:
            query["activity"] = activity
            
        cursor = collection.find(query).sort("timestamp", -1)
        
        if limit:
            cursor = cursor.limit(limit)
            
        return list(cursor)
    
    @log_call
    def delete_old_logs(self, org_code: str, collection_name: str, days_to_keep: int = 30):
        """오래된 로그를 삭제합니다."""
        cutoff_date = self.current_time - timedelta(days=days_to_keep)
        collection = self.get_collection(org_code, collection_name)
        
        result = collection.delete_many({"timestamp": {"$lt": cutoff_date}})
        # [Refactor] print를 logger.info로 교체
        logger.info(f"Deleted {result.deleted_count} old logs from {collection_name}")
        return result.deleted_count
    
    @log_call
    def get_log_statistics(self, org_code: str, collection_name: str):
        """로그 통계를 조회합니다."""
        collection = self.get_collection(org_code, collection_name)
        
        total_count = collection.count_documents({})
        
        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": self.current_time - timedelta(days=7)
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d",
                            "date": "$timestamp"
                        }
                    },
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        daily_stats = list(collection.aggregate(pipeline))
        
        return {
            "total_count": total_count,
            "daily_stats": daily_stats
        }