"""
RabbitMQ 메시지 발행자들
"""
import json
import asyncio
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractRobustChannel, AbstractExchange

from .config import RabbitMQConfig, get_rabbitmq_config
from .connection import get_channel


class BasePublisher:
    """기본 발행자 클래스"""
    
    def __init__(self, config: RabbitMQConfig = None):
        self.config = config or get_rabbitmq_config()
        self._channel = None
        self._exchanges = {}
    
    async def get_channel(self) -> AbstractRobustChannel:
        """채널 반환 (재사용)"""
        if self._channel is None or self._channel.is_closed:
            self._channel = await get_channel()
        return self._channel
    
    async def get_exchange(self, name: str, exchange_type: ExchangeType = ExchangeType.TOPIC) -> AbstractExchange:
        """Exchange 반환 (캐시됨)"""
        if name not in self._exchanges:
            channel = await self.get_channel()
            self._exchanges[name] = await channel.declare_exchange(
                name, exchange_type, durable=True
            )
        return self._exchanges[name]
    
    async def close(self):
        """리소스 정리"""
        if self._channel and not self._channel.is_closed:
            await self._channel.close()
        self._exchanges.clear()


class ChatPublisher(BasePublisher):
    """채팅 메시지 발행자"""
    
    async def publish_response(self, session_id: str, chunk: str, event: str = "message"):
        """채팅 응답 발행 (SSE용)"""
        exchange = await self.get_exchange(
            self.config.chat_responses_exchange, 
            ExchangeType.FANOUT
        )
        
        message_body = json.dumps({
            "session_id": session_id,
            "event": event,
            "data": chunk,
            "timestamp": datetime.utcnow().isoformat()
        }).encode('utf-8')
        
        message = Message(
            body=message_body,
            content_type='application/json',
            delivery_mode=DeliveryMode.PERSISTENT
        )
        
        await exchange.publish(message, routing_key=session_id)
    
    async def publish_message(self, session_id: str, user_message: str, user_id: str = None):
        """채팅 메시지 발행"""
        exchange = await self.get_exchange(
            self.config.chat_messages_exchange,
            ExchangeType.DIRECT
        )
        
        message_body = json.dumps({
            "session_id": session_id,
            "seller_msg": user_message,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat()
        }).encode('utf-8')
        
        message = Message(
            body=message_body,
            content_type='application/json',
            delivery_mode=DeliveryMode.PERSISTENT
        )
        
        await exchange.publish(message, routing_key="request")


class TaskPublisher(BasePublisher):
    """작업 발행자"""
    
    async def publish_task(self, routing_key: str, payload: Dict[str, Any]):
        """작업 발행"""
        exchange = await self.get_exchange(self.config.tasks_exchange)
        
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        message = Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        
        await exchange.publish(message, routing_key=routing_key)
    
    async def publish_result(self, routing_key: str, payload: Dict[str, Any]):
        """결과 발행"""
        exchange = await self.get_exchange(self.config.results_exchange)
        
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        message = Message(
            body=body,
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
        )
        
        await exchange.publish(message, routing_key=routing_key)


class LLMPublisher(BasePublisher):
    """LLM 스트리밍 발행자 - SSE 통신 전용"""
    
    async def publish_stream_chunk(
        self, 
        job_id: str, 
        chunk: str, 
        chunk_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None
    ):
        """LLM 스트리밍 청크 발행"""
        exchange = await self.get_exchange(
            self.config.llm_stream_exchange,
            ExchangeType.TOPIC
        )
        
        message_body = json.dumps({
            "job_id": job_id,
            "chunk": chunk,
            "chunk_type": chunk_type,
            "metadata": metadata or {},
            "timestamp": datetime.utcnow().isoformat()
        }).encode('utf-8')
        
        message = Message(
            body=message_body,
            content_type='application/json',
            delivery_mode=DeliveryMode.NOT_PERSISTENT  # 스트리밍은 휘발성
        )
        
        await exchange.publish(message, routing_key=f"llm.stream.{job_id}")
    
    async def publish_stream_complete(self, job_id: str, final_result: Any = None):
        """LLM 스트리밍 완료 신호"""
        await self.publish_stream_chunk(
            job_id=job_id,
            chunk="",
            chunk_type="complete",
            metadata={"final_result": final_result}
        )
    
    async def publish_stream_error(self, job_id: str, error: str):
        """LLM 스트리밍 에러 신호"""
        await self.publish_stream_chunk(
            job_id=job_id,
            chunk="",
            chunk_type="error",
            metadata={"error": error}
        )
    
    async def stream_llm_response(
        self,
        job_id: str,
        llm_generator: AsyncGenerator[str, None]
    ):
        """LLM 응답을 실시간으로 스트리밍"""
        try:
            async for chunk in llm_generator:
                if chunk:  # 빈 청크는 건너뛰기
                    await self.publish_stream_chunk(job_id, chunk)
                    await asyncio.sleep(0)  # 다른 태스크가 실행될 수 있게 양보
            
            await self.publish_stream_complete(job_id)
            
        except Exception as e:
            await self.publish_stream_error(job_id, str(e))
            raise