"""
MongoDB Library for NSP Chatbot

깔끔하고 모듈화된 MongoDB 클라이언트 라이브러리
각 기능이 분리되어 있어 재사용성과 유지보수성이 높음
"""

from .client import MongoDBClient
from .config import MongoConfig
from .models import MessageData, ThreadData
from .utils import generate_id, log_call
from .base_client import BaseMongoClient
from .organization_manager import OrganizationManager
from .user_manager import UserManager
from .thread_manager import ThreadManager
from .message_manager import MessageManager
from .vectorstore_manager import VectorstoreManager
from .memory_manager import MemoryManager
from .logging_manager import LoggingManager

__version__ = "1.0.0"
__author__ = "NSP Development Team"

__all__ = [
    "MongoDBClient",
    "MongoConfig",
    "MessageData",
    "ThreadData",
    "generate_id",
    "log_call",
    "BaseMongoClient",
    "OrganizationManager",
    "UserManager",
    "ThreadManager",
    "MessageManager",
    "VectorstoreManager",
    "MemoryManager",
    "LoggingManager"
]