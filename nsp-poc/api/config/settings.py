from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """Application settings"""
    
    # API Settings
    app_name: str = "NSP Chat API"
    version: str = "1.0.0"
    debug: bool = True
    
    # Server Settings
    host: str = "0.0.0.0"
    port: int = 8000
    
    # RabbitMQ Settings
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_vhost: str = "/"
    rabbitmq_url: Optional[str] = None # For direct connection string

    # RabbitMQ Topology Settings (중앙화)
    rabbitmq_chat_messages_exchange: str = "chat.messages"
    rabbitmq_chat_responses_exchange: str = "chat.responses"
    rabbitmq_tasks_exchange: str = "ai.tasks"
    rabbitmq_results_exchange: str = "ai.results"
    rabbitmq_dlx_exchange: str = "ai.dlq"
    rabbitmq_llm_stream_exchange: str = "llm.stream"

    rabbitmq_chat_queue: str = "q.chat.messages"
    rabbitmq_assist_queue: str = "q.assist"
    rabbitmq_galaxy_queue: str = "q.galaxy"
    rabbitmq_translate_queue: str = "q.translate"
    rabbitmq_sim_queue: str = "q.sim.control"
    rabbitmq_llm_stream_queue: str = "q.llm.stream"

    rabbitmq_assist_routing_key: str = "assist.*"
    rabbitmq_galaxy_routing_key: str = "galaxy.*"
    rabbitmq_translate_routing_key: str = "translate.*"
    rabbitmq_sim_routing_key: str = "sim.*"
    rabbitmq_llm_routing_key: str = "llm.*"

    rabbitmq_worker_prefetch: int = 10
    rabbitmq_dlq_suffix: str = ".dlq"
    
    # MongoDB Settings
    mongodb_url: str = Field("mongodb://localhost:27017", alias="MONGO_URI")
    mongodb_database: str = "nsp_chat"
    
    # MinIO Settings
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_secure: bool = False
    minio_bucket: str = "chat-files"
    
    # Qdrant Settings
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "chat_vectors"
    
    # Environment
    environment: str = "development"
    log_level: str = "INFO"
    
    # Langfuse Settings
    langfuse_host: Optional[str] = None
    langfuse_public_key: Optional[str] = None
    langfuse_secret_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_prefix = "NSP_"  # All environment variables will be prefixed with NSP_
        case_sensitive = True


# Global settings instance
settings = Settings()