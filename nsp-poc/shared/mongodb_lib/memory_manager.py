from typing import List
from .base_client import BaseMongoClient
from .utils import log_call, generate_id


class MemoryManager(BaseMongoClient):
    """메모리 관리 클래스 (외부 AI 의존성 제거된 버전)"""
    
    def __init__(self, config=None):
        super().__init__(config)
    
    @log_call
    def get_memory(self, og_code: str, thread_id: str):
        """지정된 스레드의 장기 메모리 및 이후 메시지 기록을 반환합니다."""
        collection = self.get_collection(og_code, "threads")
        thread = collection.find_one({"_id": thread_id})
        if not thread:
            return []

        history = []

        # 장기 메모리 처리
        raw_memory = thread.get("long_term_memory", [])
        cutoff = None
        if raw_memory:
            last_mem = raw_memory[-1]
            memory = last_mem.get("memory") if isinstance(last_mem, dict) else last_mem
            history.append({
                "role": "long_term_memory",
                "text": memory
            })
            cutoff = last_mem.get("replace_timestamp")

        # cutoff 이후의 메시지들 추가
        for msg in thread.get("messages", []):
            msg_ts = msg.get("timestamp")
            if cutoff and msg_ts <= cutoff:
                continue
            content = msg.get("content", {})
            text = content.get("text") if isinstance(content, dict) else content
            history.append({
                "role": msg.get("role"),
                "text": text
            })

        return history
    
    @log_call
    def save_long_term_memory(self, og_code: str, thread_id: str, memory_entry: dict):
        """지정된 스레드에 장기 메모리 엔트리를 저장합니다."""
        collection = self.get_collection(og_code, "threads")
        result = collection.update_one(
            {"_id": thread_id},
            {
                "$push": {"long_term_memory": memory_entry},
                "$set": {"last_timestamp": self.config.current_time}
            }
        )
        return result.modified_count > 0
    
    @log_call
    def create_memory_entry(self, memory_text: str, replace_timestamp=None) -> dict:
        """메모리 엔트리 객체를 생성합니다."""
        return {
            "msg_id": generate_id(),
            "memory": memory_text,
            "replace_timestamp": replace_timestamp or self.config.current_time,
            "timestamp": self.config.current_time
        }
    
    @log_call
    def get_long_term_memories(self, og_code: str, thread_id: str):
        """특정 스레드의 모든 장기 메모리를 조회합니다."""
        collection = self.get_collection(og_code, "threads")
        thread = collection.find_one({"_id": thread_id})
        if not thread:
            return []

        return thread.get("long_term_memory", [])
    
    @log_call
    def delete_long_term_memory(self, og_code: str, thread_id: str, memory_msg_id: str):
        """특정 장기 메모리 엔트리를 삭제합니다."""
        collection = self.get_collection(og_code, "threads")
        result = collection.update_one(
            {"_id": thread_id},
            {"$pull": {"long_term_memory": {"msg_id": memory_msg_id}}}
        )
        return result.modified_count > 0
    
    @log_call
    def analyze_message_tokens(self, messages: List[dict]) -> dict:
        """메시지들의 토큰 수를 분석합니다 (tiktoken 없이 대략적인 계산)."""
        total_tokens = 0
        total_chars = 0
        
        for msg in messages:
            content = msg.get("content", {})
            text = content.get("text") if isinstance(content, dict) else str(content)
            chars = len(text)
            # 대략적인 토큰 계산 (1토큰 ≈ 4자)
            tokens = max(1, chars // 4)
            total_tokens += tokens
            total_chars += chars
        
        return {
            "total_tokens": total_tokens,
            "total_chars": total_chars,
            "message_count": len(messages),
            "avg_tokens_per_message": total_tokens / len(messages) if messages else 0
        }
    
    @log_call
    def should_create_memory(self, messages: List[dict], trigger_token: int = 2000) -> bool:
        """메모리 생성이 필요한지 판단합니다."""
        if len(messages) < 2:
            return False
        
        analysis = self.analyze_message_tokens(messages)
        return analysis["total_tokens"] >= trigger_token