"""
메시지 관리 클래스 (리팩토링됨)
"""
from typing import List, Dict, Any
from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from .base_client import BaseMongoClient
from .utils import log_call
from .models import MessageData

logger = logging.getLogger(__name__)


class MessageManager(BaseMongoClient):
    """메시지 관리 클래스"""
    
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
    def add_user_message(self, og_code: str, thread_id: str, msg_id: str, content: Any):
        """사용자 메시지를 추가합니다."""
        return self._add_message(og_code, thread_id, msg_id, "user", content)
    
    @log_call
    def add_ai_message(self, og_code: str, thread_id: str, msg_id: str, content: Any):
        """AI 메시지를 추가하거나 업데이트합니다."""
        collection = self.get_collection(og_code, "threads")
        
        message = MessageData(
            msg_id=msg_id,
            role="ai",
            content=content,
            timestamp=self.current_time
        )

        thread = collection.find_one({"_id": thread_id})
        if not thread:
            logger.warning(f"Thread {thread_id} not found for adding AI message.")
            return False

        # 기존 AI 메시지 업데이트 시도
        result = collection.update_one(
            {
                "_id": thread_id,
                "messages.msg_id": msg_id
            },
            {
                "$set": {
                    "messages.$[m].content": content,
                    "messages.$[m].timestamp": self.current_time,
                    "last_timestamp": self.current_time
                }
            },
            array_filters=[
                {"m.msg_id": msg_id}
            ]
        )

        # 기존 메시지가 없으면 새로 추가
        if result.modified_count == 0:
            collection.update_one(
                {"_id": thread_id},
                {
                    "$push": {"messages": message.to_dict()},
                    "$set": {"last_timestamp": self.current_time}
                }
            )

        logger.info(f"[AI] Message added to thread '{thread_id}'")
        return True
    
    @log_call
    def add_system_message(self, og_code: str, thread_id: str, msg_id: str, content: Any):
        """시스템 메시지를 추가합니다."""
        return self._add_message(og_code, thread_id, msg_id, "system", content)
    
    def _add_message(self, og_code: str, thread_id: str, msg_id: str, role: str, content: Any):
        """공통 메시지 추가 로직"""
        collection = self.get_collection(og_code, "threads")
        
        message = MessageData(
            msg_id=msg_id,
            role=role,
            content=content,
            timestamp=self.current_time
        )

        thread = collection.find_one({"_id": thread_id})
        if not thread:
            logger.warning(f"Thread {thread_id} not found for adding {role} message.")
            return False

        collection.update_one(
            {"_id": thread_id},
            {
                "$push": {"messages": message.to_dict()},
                "$set": {"last_timestamp": self.current_time}
            }
        )

        logger.info(f"[{role.upper()}] Message added to thread '{thread_id}'")
        return True
    
    @log_call
    def get_thread_messages(self, org_code: str, thread_id: str):
        """특정 스레드의 메시지 목록을 반환합니다."""
        collection = self.get_collection(org_code, "threads")
        thread = collection.find_one({"_id": thread_id})
        if not thread:
            return []
        
        return thread.get("messages", [])
    
    @log_call
    def get_history(self, og_code: str, thread_id: str):
        """지정된 스레드의 메시지 기록을 순서대로 반환합니다."""
        collection = self.get_collection(og_code, "threads")
        thread = collection.find_one({"_id": thread_id})
        if not thread:
            return []

        history = []
        for msg in thread.get("messages", []):
            content = msg.get("content", {})
            text = content.get("text") if isinstance(content, dict) else content
            history.append({
                "role": msg.get("role"),
                "text": text,
            })
        return history
    
    @log_call
    def delete_message(self, org_code: str, thread_id: str, msg_id: str):
        """특정 메시지를 삭제합니다."""
        collection = self.get_collection(org_code, "threads")
        result = collection.update_one(
            {"_id": thread_id},
            {"$pull": {"messages": {"msg_id": msg_id}}}
        )
        return result.modified_count > 0