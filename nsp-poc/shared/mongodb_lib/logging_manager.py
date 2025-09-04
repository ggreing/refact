from typing import Dict
from .base_client import BaseMongoClient
from .utils import log_call


class LoggingManager(BaseMongoClient):
    """로그 관리 클래스"""
    
    def __init__(self, config=None):
        super().__init__(config)
    
    @log_call
    def log_error(self, org_code: str, error_data: dict):
        """에러 로그를 저장합니다."""
        collection = self.get_collection(org_code, "error_log")
        error_entry = {
            "error_data": error_data,
            "timestamp": self.config.current_time
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
            "timestamp": self.config.current_time
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
        from datetime import timedelta
        
        cutoff_date = self.config.current_time - timedelta(days=days_to_keep)
        collection = self.get_collection(org_code, collection_name)
        
        result = collection.delete_many({"timestamp": {"$lt": cutoff_date}})
        print(f"Deleted {result.deleted_count} old logs from {collection_name}")
        return result.deleted_count
    
    @log_call
    def get_log_statistics(self, org_code: str, collection_name: str):
        """로그 통계를 조회합니다."""
        collection = self.get_collection(org_code, collection_name)
        
        total_count = collection.count_documents({})
        
        # 날짜별 통계 (최근 7일)
        from datetime import timedelta
        
        pipeline = [
            {
                "$match": {
                    "timestamp": {
                        "$gte": self.config.current_time - timedelta(days=7)
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