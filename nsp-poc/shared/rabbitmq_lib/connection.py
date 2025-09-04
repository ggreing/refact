"""
RabbitMQ 연결 관리
"""
import aio_pika
from aio_pika.abc import AbstractRobustConnection, AbstractRobustChannel
from .config import RabbitMQConfig, get_rabbitmq_config


class ConnectionManager:
    """RabbitMQ 연결 관리 클래스"""
    
    def __init__(self, config: RabbitMQConfig = None):
        self.config = config or get_rabbitmq_config()
        self._connection = None
    
    async def get_connection(self) -> AbstractRobustConnection:
        """RabbitMQ 연결 반환 (재사용)"""
        if self._connection is None or self._connection.is_closed:
            if self.config.url:
                self._connection = await aio_pika.connect_robust(self.config.url)
            else:
                self._connection = await aio_pika.connect_robust(
                    host=self.config.host,
                    port=self.config.port,
                    login=self.config.user,
                    password=self.config.password,
                    virtualhost=self.config.vhost,
                )
        return self._connection
    
    async def get_channel(self) -> AbstractRobustChannel:
        """새로운 채널 생성"""
        connection = await self.get_connection()
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=self.config.worker_prefetch)
        return channel
    
    async def close(self):
        """연결 종료"""
        if self._connection and not self._connection.is_closed:
            await self._connection.close()


# 전역 연결 관리자
_connection_manager = None


async def get_rabbitmq_connection() -> AbstractRobustConnection:
    """전역 RabbitMQ 연결 반환 (기존 호환성)"""
    global _connection_manager
    if _connection_manager is None:
        _connection_manager = ConnectionManager()
    return await _connection_manager.get_connection()


async def get_channel() -> AbstractRobustChannel:
    """새로운 채널 생성 (기존 호환성)"""
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