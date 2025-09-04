"""
RabbitMQ 메시지 소비자들 (리팩토링됨)
"""
import json
import asyncio
import logging
from typing import Callable, Dict, Any, Optional, List, AsyncIterator
from datetime import datetime

import aio_pika
from aio_pika.abc import AbstractRobustChannel, AbstractQueue, AbstractIncomingMessage

from api.config.settings import settings
from .connection import get_channel

logger = logging.getLogger(__name__)


class BaseConsumer:
    """기본 소비자 클래스"""
    
    def __init__(self):
        self.config = settings
        self._channel = None
        self._consuming = False
    
    async def get_channel(self) -> AbstractRobustChannel:
        """채널 반환 (재사용)"""
        if self._channel is None or self._channel.is_closed:
            self._channel = await get_channel()
        return self._channel
    
    async def close(self):
        """리소스 정리"""
        self._consuming = False
        if self._channel and not self._channel.is_closed:
            await self._channel.close()


class ChatConsumer(BaseConsumer):
    """채팅 메시지 소비자"""
    
    async def consume_messages(
        self,
        callback: Callable[[Dict[str, Any]], Any],
        shutdown_event: Optional[asyncio.Event] = None
    ):
        """채팅 메시지 소비"""
        channel = await self.get_channel()
        queue = await channel.declare_queue(self.config.rabbitmq_chat_queue, durable=True)
        
        async def message_handler(message: AbstractIncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    await callback(payload)
                except Exception as e:
                    logger.error(f"Error processing chat message: {e}", exc_info=True)
        
        self._consuming = True
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if shutdown_event and shutdown_event.is_set():
                    logger.info("Shutdown event received, stopping chat consumer.")
                    await message.nack()
                    break
                
                if not self._consuming:
                    break
                
                asyncio.create_task(message_handler(message))
    
    async def consume_responses(
        self,
        session_id: str,
        callback: Callable[[Dict[str, Any]], Any],
        timeout: float = 30.0
    ):
        """특정 세션의 채팅 응답 소비 (SSE용)"""
        channel = await self.get_channel()
        
        queue_name = f"temp_responses_{session_id}"
        queue = await channel.declare_queue(queue_name, exclusive=True, auto_delete=True)
        
        exchange = await channel.declare_exchange(
            self.config.rabbitmq_chat_responses_exchange,
            aio_pika.ExchangeType.FANOUT, 
            durable=True
        )
        await queue.bind(exchange, routing_key=session_id)
        
        async def response_handler(message: AbstractIncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    if payload.get("session_id") == session_id:
                        await callback(payload)
                except Exception as e:
                    logger.error(f"Error processing chat response for session {session_id}: {e}", exc_info=True)
        
        try:
            await asyncio.wait_for(
                self._consume_until_complete(queue, response_handler),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Chat response consumption timed out for session {session_id}")
    
    async def _consume_until_complete(self, queue: AbstractQueue, handler: Callable):
        """완료 신호가 올 때까지 소비"""
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await handler(message)
                
                try:
                    payload = json.loads(message.body.decode())
                    if payload.get("event") in ["end", "complete", "error", "done"]:
                        break
                except:
                    pass


class TaskConsumer(BaseConsumer):
    """작업 소비자"""
    
    async def consume_tasks(
        self,
        queue_name: str,
        callback: Callable[[Dict[str, Any]], Any],
        shutdown_event: Optional[asyncio.Event] = None
    ):
        """특정 큐의 작업 소비"""
        channel = await self.get_channel()
        queue = await channel.declare_queue(queue_name, durable=True)
        
        async def task_handler(message: AbstractIncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    await callback(payload)
                except Exception as e:
                    logger.error(f"Error processing task from queue {queue_name}: {e}", exc_info=True)
        
        self._consuming = True
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                if shutdown_event and shutdown_event.is_set():
                    logger.info(f"Shutdown event received, stopping task consumer for queue {queue_name}.")
                    await message.nack()
                    break
                
                if not self._consuming:
                    break
                
                asyncio.create_task(task_handler(message))
    
    async def consume_results(
        self,
        routing_key_pattern: str,
        callback: Callable[[Dict[str, Any]], Any],
        timeout: float = 60.0
    ):
        """작업 결과 소비"""
        channel = await self.get_channel()
        
        queue = await channel.declare_queue("", exclusive=True, auto_delete=True)
        
        exchange = await channel.declare_exchange(
            self.config.rabbitmq_results_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        await queue.bind(exchange, routing_key=routing_key_pattern)
        
        async def result_handler(message: AbstractIncomingMessage):
            async with message.process():
                try:
                    payload = json.loads(message.body.decode())
                    await callback(payload)
                except Exception as e:
                    logger.error(f"Error processing result for pattern {routing_key_pattern}: {e}", exc_info=True)
        
        try:
            await asyncio.wait_for(
                self._consume_results_until_complete(queue, result_handler),
                timeout=timeout
            )
        except asyncio.TimeoutError:
            logger.warning(f"Result consumption timed out for pattern {routing_key_pattern}")
    
    async def _consume_results_until_complete(self, queue: AbstractQueue, handler: Callable):
        """결과 완료까지 소비"""
        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                await handler(message)
                
                try:
                    payload = json.loads(message.body.decode())
                    message_type = payload.get("type", "")
                    if message_type in ["done", "error", "completed", "failed"]:
                        break
                except:
                    pass


class LLMConsumer(BaseConsumer):
    """LLM 스트리밍 소비자 - SSE 통신 전용"""
    
    async def consume_stream(
        self,
        job_id: str,
        callback: Callable[[Dict[str, Any]], Any],
        timeout: float = 120.0
    ) -> AsyncIterator[Dict[str, Any]]:
        """LLM 스트림 소비 (AsyncIterator로 반환)"""
        channel = await self.get_channel()
        
        queue_name = f"temp_llm_stream_{job_id}"
        queue = await channel.declare_queue(queue_name, exclusive=True, auto_delete=True)
        
        exchange = await channel.declare_exchange(
            self.config.rabbitmq_llm_stream_exchange,
            aio_pika.ExchangeType.TOPIC,
            durable=True
        )
        await queue.bind(exchange, routing_key=f"llm.stream.{job_id}")
        
        async def stream_generator():
            try:
                async with queue.iterator() as queue_iter:
                    async for message in queue_iter:
                        async with message.process():
                            try:
                                payload = json.loads(message.body.decode())
                                
                                if callback:
                                    await callback(payload)
                                
                                yield payload
                                
                                chunk_type = payload.get("chunk_type", "text")
                                if chunk_type in ["complete", "error"]:
                                    break
                                    
                            except Exception as e:
                                error_payload = {
                                    "job_id": job_id, "chunk": "", "chunk_type": "error",
                                    "metadata": {"error": str(e)}, "timestamp": datetime.utcnow().isoformat()
                                }
                                logger.error(f"Error processing stream chunk for job {job_id}: {e}", exc_info=True)
                                yield error_payload
                                break
            
            except Exception as e:
                error_payload = {
                    "job_id": job_id, "chunk": "", "chunk_type": "error",
                    "metadata": {"error": str(e)}, "timestamp": datetime.utcnow().isoformat()
                }
                logger.error(f"Error in stream generator for job {job_id}: {e}", exc_info=True)
                yield error_payload
        
        try:
            async for item in asyncio.wait_for(stream_generator(), timeout=timeout):
                yield item
        except asyncio.TimeoutError:
            logger.warning(f"Stream consumption timed out for job {job_id}")
            yield {
                "job_id": job_id, "chunk": "", "chunk_type": "error",
                "metadata": {"error": "Stream consumption timed out"}, "timestamp": datetime.utcnow().isoformat()
            }
    
    async def create_sse_stream(
        self,
        job_id: str,
        timeout: float = 120.0
    ) -> AsyncIterator[str]:
        """SSE 형식의 스트림 생성"""
        async for payload in self.consume_stream(job_id, None, timeout):
            chunk_type = payload.get("chunk_type", "text")
            
            if chunk_type == "text":
                sse_data = f"data: {json.dumps(payload)}\n\n"
            elif chunk_type == "complete":
                sse_data = f"event: complete\ndata: {json.dumps(payload)}\n\n"
            elif chunk_type == "error":
                sse_data = f"event: error\ndata: {json.dumps(payload)}\n\n"
            else:
                sse_data = f"data: {json.dumps(payload)}\n\n"
            
            yield sse_data
            
            if chunk_type in ["complete", "error"]:
                break