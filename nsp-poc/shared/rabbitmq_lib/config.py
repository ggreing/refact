"""
RabbitMQ 설정 관리
"""
import os
from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class RabbitMQConfig:
    """RabbitMQ 연결 및 토폴로지 설정"""
    host: str
    port: int
    user: str
    password: str
    vhost: str
    url: str = None
    
    # Exchange 설정
    chat_messages_exchange: str = "chat.messages"
    chat_responses_exchange: str = "chat.responses"
    tasks_exchange: str = "ai.tasks"
    results_exchange: str = "ai.results"
    dlx_exchange: str = "ai.dlq"
    llm_stream_exchange: str = "llm.stream"  # LLM 스트리밍용
    
    # Queue 설정
    chat_queue: str = "q.chat.messages"
    assist_queue: str = "q.assist"
    galaxy_queue: str = "q.galaxy"
    translate_queue: str = "q.translate"
    sim_queue: str = "q.sim.control"
    llm_stream_queue: str = "q.llm.stream"  # LLM 스트리밍용
    
    # Routing Key 설정
    assist_routing_key: str = "assist.*"
    galaxy_routing_key: str = "galaxy.*"
    translate_routing_key: str = "translate.*"
    sim_routing_key: str = "sim.*"
    llm_routing_key: str = "llm.*"  # LLM 스트리밍용
    
    # 기타 설정
    worker_prefetch: int = 10
    dlq_suffix: str = ".dlq"


def get_rabbitmq_config() -> RabbitMQConfig:
    """환경변수에서 RabbitMQ 설정을 로드"""
    return RabbitMQConfig(
        host=os.getenv("RABBITMQ_HOST", "rabbitmq"),
        port=int(os.getenv("RABBITMQ_PORT", 5672)),
        user=os.getenv("RABBITMQ_USER", "guest"),
        password=os.getenv("RABBITMQ_PASSWORD", "guest"),
        vhost=os.getenv("RABBITMQ_VHOST", "/"),
        url=os.getenv("RABBITMQ_URL"),
        
        # Exchange 설정 (환경변수로 오버라이드 가능)
        tasks_exchange=os.getenv("TASKS_EXCHANGE", "ai.tasks"),
        results_exchange=os.getenv("RESULTS_EXCHANGE", "ai.results"),
        dlx_exchange=os.getenv("DLX_EXCHANGE", "ai.dlq"),
        
        # Queue 설정
        assist_queue=os.getenv("Q_ASSIST", "q.assist"),
        galaxy_queue=os.getenv("Q_GALAXY", "q.galaxy"),
        translate_queue=os.getenv("Q_TRANSLATE", "q.translate"),
        sim_queue=os.getenv("Q_SIM", "q.sim.control"),
        
        # Routing Key 설정
        assist_routing_key=os.getenv("RK_ASSIST", "assist.*"),
        galaxy_routing_key=os.getenv("RK_GALAXY", "galaxy.*"),
        translate_routing_key=os.getenv("RK_TRANSLATE", "translate.*"),
        sim_routing_key=os.getenv("RK_SIM", "sim.*"),
        
        # 기타 설정
        worker_prefetch=int(os.getenv("WORKER_PREFETCH", "10")),
    )