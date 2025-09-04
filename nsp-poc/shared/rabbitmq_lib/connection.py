"""
RabbitMQ 연결 관리 (리팩토링됨)
"""
import aio_pika
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel

# [Refactor] 분산된 설정 대신 중앙 설정 객체를 import
from api.config.settings import settings


class ConnectionManager:
    """RabbitMQ 연결 관리 클래스"""
    
    def __init__(self):
        # [Refactor] 중앙 설정 객체를 직접 사용
        self.config = settings
        self._connection = None
    
    async def get_connection(self) -> AbstractRobustConnection:
        """RabbitMQ 연결 반환 (재사용)"""
        if self._connection is None or self._connection.is_closed:
            # [Refactor] 중앙 설정의 필드 이름을 사용하도록 수정
            if self.config.rabbitmq_url:
                self._connection = await aio_pika.connect_robust(self.config.rabbitmq_url)
            else:
                self._connection = await aio_pika.connect_robust(
                    host=self.config.rabbitmq_host,
                    port=self.config.rabbitmq_port,
                    login=self.config.rabbitmq_user,
                    password=self.config.rabbitmq_password,
                    virtualhost=self.config.rabbitmq_vhost,
                )
        return self._connection
    
    async def get_channel(self) -> AbstractRobustChannel:
        """새로운 채널 생성"""
        connection = await self.get_connection()
        channel = await connection.channel()
        # [Refactor] 중앙 설정의 필드 이름을 사용하도록 수정
        await channel.set_qos(prefetch_count=self.config.rabbitmq_worker_prefetch)
        return channel
    
    async def close(self):
        """연결 종료"""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()


# 전역 연결 관리자 (기존 구조 유지)
_connection_manager = None


async def get_rabbitmq_connection() -> AbstractRobustConnection:
    """전역 RabbitMQ 연결 반환"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return await _connection_manager.get_connection()


async def get_channel() -> AbstractRobustChannel:
    """새로운 채널 생성"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return await _connection_manager.get_channel()


async def close_connection():
    """전역 연결 종료"""
    global _connection_manager
    if _connection_manager:
        await _connection_manager.close()
        _connection_manager = None