"""
RabbitMQ 토폴로지 관리
Exchange, Queue, Binding 선언
"""
from typing import Dict, Any
import aio_pika
from aio_pika import ExchangeType
from aio_pika.abc import AbstractRobustChannel, AbstractQueue

from .config import RabbitMQConfig, get_rabbitmq_config


async def _compat_declare_exchange(
    channel: AbstractRobustChannel, 
    name: str, 
    exchange_type: ExchangeType, 
    durable: bool = True
):
    """호환성을 위한 Exchange 선언"""
    if hasattr(channel, "declare_exchange"):
        return await channel.declare_exchange(name, exchange_type, durable=durable)
    elif hasattr(channel, "exchange_declare"):
        type_str = exchange_type.value.lower() if hasattr(exchange_type, "value") else str(exchange_type).lower()
        return await channel.exchange_declare(exchange=name, exchange_type=type_str, durable=durable)
    else:
        raise AttributeError("Channel has neither declare_exchange nor exchange_declare")


async def declare_chat_topology(channel: AbstractRobustChannel, config: RabbitMQConfig = None) -> Dict[str, AbstractQueue]:
    """채팅 관련 토폴로지 선언"""
    config = config or get_rabbitmq_config()
    
    # Chat Messages Exchange (Direct)
    await _compat_declare_exchange(
        channel, 
        config.chat_messages_exchange, 
        ExchangeType.DIRECT, 
        durable=True
    )
    
    # Chat Responses Exchange (Fanout) 
    await _compat_declare_exchange(
        channel,
        config.chat_responses_exchange,
        ExchangeType.FANOUT,
        durable=True
    )
    
    # Chat Queue
    chat_queue = await channel.declare_queue(config.chat_queue, durable=True)
    await chat_queue.bind(config.chat_messages_exchange, routing_key="request")
    
    return {"chat": chat_queue}


async def declare_worker_topology(channel: AbstractRobustChannel, config: RabbitMQConfig = None) -> Dict[str, AbstractQueue]:
    """워커 관련 토폴로지 선언"""
    config = config or get_rabbitmq_config()
    
    # Worker Exchanges
    await _compat_declare_exchange(channel, config.tasks_exchange, ExchangeType.TOPIC, durable=True)
    await _compat_declare_exchange(channel, config.results_exchange, ExchangeType.TOPIC, durable=True)
    await _compat_declare_exchange(channel, config.dlx_exchange, ExchangeType.FANOUT, durable=True)
    
    # Main Worker Queues (without DLX for now to avoid conflicts)
    q_assist = await channel.declare_queue(config.assist_queue, durable=True)
    q_galaxy = await channel.declare_queue(config.galaxy_queue, durable=True)
    q_translate = await channel.declare_queue(config.translate_queue, durable=True)
    q_sim = await channel.declare_queue(config.sim_queue, durable=True)
    
    # Bindings to Tasks Exchange
    await q_assist.bind(config.tasks_exchange, config.assist_routing_key)
    await q_galaxy.bind(config.tasks_exchange, config.galaxy_routing_key)
    await q_translate.bind(config.tasks_exchange, config.translate_routing_key)
    await q_sim.bind(config.tasks_exchange, config.sim_routing_key)
    
    # Dead Letter Queues
    await channel.declare_queue(f"{config.assist_queue}{config.dlq_suffix}", durable=True)
    await channel.declare_queue(f"{config.galaxy_queue}{config.dlq_suffix}", durable=True)
    await channel.declare_queue(f"{config.translate_queue}{config.dlq_suffix}", durable=True)
    await channel.declare_queue(f"{config.sim_queue}{config.dlq_suffix}", durable=True)
    
    return {
        "assist": q_assist,
        "galaxy": q_galaxy,
        "translate": q_translate,
        "sim": q_sim,
    }


async def declare_llm_topology(channel: AbstractRobustChannel, config: RabbitMQConfig = None) -> Dict[str, AbstractQueue]:
    """LLM 스트리밍 관련 토폴로지 선언"""
    config = config or get_rabbitmq_config()
    
    # LLM Stream Exchange (Topic) - SSE용
    await _compat_declare_exchange(
        channel,
        config.llm_stream_exchange, 
        ExchangeType.TOPIC,
        durable=True
    )
    
    # LLM Stream Queue (선택적, 필요시에만)
    # 보통은 임시 큐를 사용하지만, 영구 큐가 필요한 경우
    llm_queue = await channel.declare_queue(
        config.llm_stream_queue, 
        durable=False,  # 스트리밍은 휘발성
        auto_delete=True
    )
    
    # 기본 바인딩 (모든 LLM 스트림)
    await llm_queue.bind(config.llm_stream_exchange, config.llm_routing_key)
    
    return {"llm_stream": llm_queue}


async def declare_ai_worker_topology(channel: AbstractRobustChannel, config: RabbitMQConfig = None) -> Dict[str, AbstractQueue]:
    """AI 워커 토폴로지 선언 (새로운 구조)"""
    config = config or get_rabbitmq_config()
    
    # Main routing queue - API에서 여기로 메시지 발행
    routing_queue = await channel.declare_queue("message_routing_queue", durable=True)
    
    # AI function specific queues
    chat_queue = await channel.declare_queue("chat_processing_queue", durable=True)
    translate_queue = await channel.declare_queue("translate_processing_queue", durable=True)
    summarize_queue = await channel.declare_queue("summarize_processing_queue", durable=True) 
    search_queue = await channel.declare_queue("search_processing_queue", durable=True)
    
    # Stream exchanges for real-time responses
    await _compat_declare_exchange(channel, "chat_stream_exchange", ExchangeType.TOPIC, durable=True)
    await _compat_declare_exchange(channel, "translate_stream_exchange", ExchangeType.TOPIC, durable=True)
    await _compat_declare_exchange(channel, "summarize_stream_exchange", ExchangeType.TOPIC, durable=True)
    await _compat_declare_exchange(channel, "search_stream_exchange", ExchangeType.TOPIC, durable=True)
    
    return {
        "routing": routing_queue,
        "chat_processing": chat_queue,
        "translate_processing": translate_queue,
        "summarize_processing": summarize_queue,
        "search_processing": search_queue
    }


async def declare_topology(channel: AbstractRobustChannel, config: RabbitMQConfig = None) -> Dict[str, AbstractQueue]:
    """모든 토폴로지를 선언하는 통합 함수"""
    config = config or get_rabbitmq_config()
    
    # 각 토폴로지 선언
    chat_queues = await declare_chat_topology(channel, config)
    worker_queues = await declare_worker_topology(channel, config)
    llm_queues = await declare_llm_topology(channel, config)
    ai_worker_queues = await declare_ai_worker_topology(channel, config)
    
    # 결과 통합
    all_queues = {}
    all_queues.update(chat_queues)
    all_queues.update(worker_queues)
    all_queues.update(llm_queues)
    all_queues.update(ai_worker_queues)
    
    return all_queues


async def cleanup_topology(channel: AbstractRobustChannel, config: RabbitMQConfig = None):
    """토폴로지 정리 (개발/테스트용)"""
    config = config or get_rabbitmq_config()
    
    # 주의: 운영 환경에서는 사용하지 말 것!
    try:
        # 임시 큐들 정리 (자동 삭제되는 것들)
        pass  # 대부분 auto_delete=True로 설정되어 자동 정리됨
        
    except Exception as e:
        print(f"Cleanup failed: {e}")


async def get_queue_info(channel: AbstractRobustChannel, queue_name: str) -> Dict[str, Any]:
    """큐 정보 조회"""
    try:
        # RabbitMQ Management API를 통해 더 자세한 정보를 얻을 수 있지만
        # 기본적으로는 큐 선언을 통해 존재 여부만 확인
        queue = await channel.declare_queue(queue_name, passive=True)
        return {
            "name": queue_name,
            "exists": True,
            "queue": queue
        }
    except Exception as e:
        return {
            "name": queue_name,
            "exists": False,
            "error": str(e)
        }