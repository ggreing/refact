"""
Server-Sent Events (SSE) 지원 모듈
RabbitMQ와 SSE 연결을 위한 브릿지
"""
import json
import asyncio
from typing import Dict, Any, AsyncIterator, Optional, Callable
from datetime import datetime, timezone

from .consumer import LLMConsumer
from .publisher import LLMPublisher
from .config import RabbitMQConfig, get_rabbitmq_config


class SSEBridge:
    """RabbitMQ와 SSE 간의 브릿지 클래스"""
    
    def __init__(self, config: RabbitMQConfig = None):
        self.config = config or get_rabbitmq_config()
        self.consumer = LLMConsumer(config)
        self.publisher = LLMPublisher(config)
    
    async def create_job_stream(
        self,
        job_id: str,
        timeout: float = 120.0,
        on_chunk: Optional[Callable[[Dict[str, Any]], None]] = None
    ) -> AsyncIterator[str]:
        """특정 job_id에 대한 SSE 스트림 생성"""
        async for sse_data in self.consumer.create_sse_stream(job_id, timeout):
            # 선택적으로 청크 콜백 호출
            if on_chunk and sse_data.startswith("data:"):
                try:
                    data_line = sse_data.strip().replace("data: ", "")
                    if data_line:
                        chunk_data = json.loads(data_line)
                        on_chunk(chunk_data)
                except:
                    pass
            
            yield sse_data
    
    async def publish_llm_stream(
        self,
        job_id: str,
        llm_response_generator: AsyncIterator[str]
    ):
        """LLM 응답을 RabbitMQ로 스트리밍"""
        await self.publisher.stream_llm_response(job_id, llm_response_generator)
    
    async def close(self):
        """리소스 정리"""
        await self.consumer.close()
        await self.publisher.close()


class SSEHandler:
    """SSE 핸들러 - FastAPI와 함께 사용"""
    
    def __init__(self, bridge: SSEBridge = None):
        self.bridge = bridge or SSEBridge()
        self._active_streams = set()
    
    async def handle_job_stream(
        self,
        job_id: str,
        timeout: float = 120.0,
        include_heartbeat: bool = True,
        heartbeat_interval: float = 30.0
    ) -> AsyncIterator[str]:
        """Job 스트림 처리 (heartbeat 포함)"""
        self._active_streams.add(job_id)
        
        try:
            # Heartbeat 태스크 시작
            heartbeat_task = None
            if include_heartbeat:
                heartbeat_task = asyncio.create_task(
                    self._send_heartbeat(job_id, heartbeat_interval)
                )
            
            # 실제 데이터 스트림
            async for data in self.bridge.create_job_stream(job_id, timeout):
                if job_id in self._active_streams:
                    yield data
                else:
                    break
            
            # Heartbeat 태스크 정리
            if heartbeat_task:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass
        
        finally:
            self._active_streams.discard(job_id)
    
    async def _send_heartbeat(self, job_id: str, interval: float):
        """하트비트 전송 (연결 유지용)"""
        try:
            while job_id in self._active_streams:
                await asyncio.sleep(interval)
                if job_id in self._active_streams:
                    # 단순한 heartbeat 메시지
                    heartbeat_data = {
                        "job_id": job_id,
                        "type": "heartbeat",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    yield f"event: heartbeat\ndata: {json.dumps(heartbeat_data)}\n\n"
        except asyncio.CancelledError:
            pass
    
    def stop_stream(self, job_id: str):
        """특정 스트림 중지"""
        self._active_streams.discard(job_id)
    
    def stop_all_streams(self):
        """모든 스트림 중지"""
        self._active_streams.clear()
    
    async def close(self):
        """핸들러 정리"""
        self.stop_all_streams()
        await self.bridge.close()


# 편의 함수들
async def create_sse_stream_for_job(
    job_id: str,
    timeout: float = 120.0,
    config: RabbitMQConfig = None
) -> AsyncIterator[str]:
    """간단한 SSE 스트림 생성 함수"""
    bridge = SSEBridge(config)
    try:
        async for data in bridge.create_job_stream(job_id, timeout):
            yield data
    finally:
        await bridge.close()


async def publish_llm_to_sse(
    job_id: str,
    llm_generator: AsyncIterator[str],
    config: RabbitMQConfig = None
):
    """LLM 생성기를 SSE로 발행하는 편의 함수"""
    bridge = SSEBridge(config)
    try:
        await bridge.publish_llm_stream(job_id, llm_generator)
    finally:
        await bridge.close()