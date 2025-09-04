from .config import MongoConfig
from .organization_manager import OrganizationManager
from .user_manager import UserManager
from .thread_manager import ThreadManager
from .message_manager import MessageManager
from .vectorstore_manager import VectorstoreManager
from .memory_manager import MemoryManager
from .logging_manager import LoggingManager
from .utils import generate_id


class MongoDBClient:
    """통합 MongoDB 클라이언트"""
    
    def __init__(self, mongo_uri: str = None, log_level: int = None):
        self.config = MongoConfig(mongo_uri=mongo_uri, log_level=log_level)
        
        # 각 매니저 인스턴스 생성
        self.organizations = OrganizationManager(self.config)
        self.users = UserManager(self.config)
        self.threads = ThreadManager(self.config)
        self.messages = MessageManager(self.config)
        self.vectorstore = VectorstoreManager(self.config)
        self.memory = MemoryManager(self.config)
        self.logging = LoggingManager(self.config)
    
    def generate_id(self) -> str:
        """고유 ID 생성"""
        return generate_id()
    
    def close(self):
        """모든 연결 종료"""
        self.organizations.close()
        self.users.close()
        self.threads.close()
        self.messages.close()
        self.vectorstore.close()
        self.memory.close()
        self.logging.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

# === 중앙화된 MongoDB 클라이언트 접근자 (기능 변경 없음) ===
import os
_MDB_SINGLETON = None
def get_mongodb_client():
    global _MDB_SINGLETON
    if _MDB_SINGLETON is None:
        mongo_uri = os.getenv('MONGO_URI', 'mongodb://mongo:27017')
        _MDB_SINGLETON = MongoDBClient(mongo_uri=mongo_uri)
    return _MDB_SINGLETON
