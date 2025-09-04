"""
MongoDB Library 사용 예제 (로깅 적용)

이 파일은 MongoDB 라이브러리의 기본 사용법을 보여줍니다.
"""
import logging
from mongodb_lib import MongoDBClient

# 로거 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def example_basic_usage():
    """기본 사용법 예제"""
    
    # MongoDB 클라이언트 생성
    # [Refactor] Step 2에서 리팩토링된 MongoDBClient는 mongo_uri를 필수로 받음
    # 이 예제는 환경변수 MONGO_URI에 의존하게 됨.
    try:
        client = MongoDBClient()
    except ValueError as e:
        logger.error(f"MongoDBClient 생성 실패: {e}. MONGO_URI 환경변수를 설정해주세요.")
        return

    try:
        # 1. 조직 관리
        logger.info("=== Organization Management ===")
        org_name = "Example Organization"
        org_code = "example_org"
        org_key = "example_key_123"
        
        client.organizations.create_og_entry(org_name, org_code, org_key)
        org_entry = client.organizations.get_og_entry(org_code)
        logger.info(f"Organization: {org_entry}")
        
        is_valid = client.organizations.verify_og_key(org_code, org_key)
        logger.info(f"Key valid: {is_valid}")
        
        # 2. 사용자 관리
        logger.info("\n=== User Management ===")
        user_id = "user_123"
        user_name = "John Doe"
        
        client.users.create_user(org_code, user_name, user_id)
        user = client.users.get_user(org_code, user_id)
        logger.info(f"User: {user}")
        
        # 3. 스레드 관리
        logger.info("\n=== Thread Management ===")
        function_name = "chat_function"
        
        thread_id = client.threads.add_user_thread(org_code, user_id, function_name)
        logger.info(f"Created thread: {thread_id}")
        
        threads = client.threads.get_user_threads(org_code, user_id, function_name)
        logger.info(f"User threads: {threads}")
        
        # 4. 메시지 관리
        logger.info("\n=== Message Management ===")
        msg_id = client.generate_id()
        client.messages.add_user_message(org_code, thread_id, msg_id, "Hello, AI!")
        
        ai_msg_id = client.generate_id()
        client.messages.add_ai_message(org_code, thread_id, ai_msg_id, "Hello! How can I help you?")
        
        history = client.messages.get_history(org_code, thread_id)
        logger.info(f"Message history: {history}")
        
        # 5. 벡터스토어 관리
        logger.info("\n=== Vectorstore Management ===")
        vector_id = "vector_123"
        files = [
            {
                "filename": "document1.pdf",
                "file_hash": "abc123",
                "file_size": 1024,
                "uploaded_at": client.messages.current_time  # MessageManager의 current_time 사용
            }
        ]
        
        client.vectorstore.add_vectorstore(org_code, vector_id, files)
        client.vectorstore.set_thread_vectorstore(org_code, thread_id, vector_id)
        
        # 6. 로깅
        logger.info("\n=== Logging ===")
        client.logging.log_user_activity(org_code, user_id, "chat_started", {"thread_id": thread_id})
        
        error_data = {
            "error_type": "validation_error",
            "message": "Invalid input format",
            "user_id": user_id
        }
        client.logging.log_error(org_code, error_data)
        
        recent_activities = client.logging.get_user_activities(org_code, user_id, limit=5)
        logger.info(f"Recent activities count: {len(recent_activities)}")
        
        error_logs = client.logging.get_error_logs(org_code, limit=5)
        logger.info(f"Recent errors count: {len(error_logs)}")
        
        logger.info("\n=== Example completed successfully ===")
        
    except Exception as e:
        logger.error(f"Error occurred: {e}", exc_info=True)
    
    finally:
        if 'client' in locals():
            client.close()


def example_context_manager():
    """컨텍스트 매니저 사용 예제"""
    try:
        with MongoDBClient() as client:
            org_code = "test_org"
            client.organizations.create_og_entry("Test Org", org_code, "test_key")
            client.users.create_user(org_code, "Test User", "test_user")
            logger.info("Context manager example completed")
    except ValueError as e:
        logger.error(f"MongoDBClient 생성 실패: {e}. MONGO_URI 환경변수를 설정해주세요.")


def example_memory_management():
    """메모리 관리 예제"""
    try:
        with MongoDBClient() as client:
            org_code = "memory_test_org"
            user_id = "memory_user"
            
            client.organizations.create_og_entry("Memory Test Org", org_code, "memory_key")
            client.users.create_user(org_code, "Memory User", user_id)
            
            thread_id = client.threads.add_user_thread(org_code, user_id, "memory_chat")
            
            for i in range(5):
                user_msg_id = client.generate_id()
                ai_msg_id = client.generate_id()
                client.messages.add_user_message(org_code, thread_id, user_msg_id, f"User message {i}")
                client.messages.add_ai_message(org_code, thread_id, ai_msg_id, f"AI response {i}")

            messages = client.messages.get_thread_messages(org_code, thread_id)
            should_create = client.memory.should_create_memory(messages, trigger_token=50)
            logger.info(f"Should create memory: {should_create}")

            if should_create:
                memory_entry = client.memory.create_memory_entry("Summary of conversation about topics 1-5")
                client.memory.save_long_term_memory(org_code, thread_id, memory_entry)

                memories = client.memory.get_long_term_memories(org_code, thread_id)
                logger.info(f"Long term memories: {len(memories)}")

                full_history = client.memory.get_memory(org_code, thread_id)
                logger.info(f"Full history with memory: {len(full_history)} items")

            logger.info("Memory management example completed")
    except ValueError as e:
        logger.error(f"MongoDBClient 생성 실패: {e}. MONGO_URI 환경변수를 설정해주세요.")


if __name__ == "__main__":
    logger.info("MongoDB Library Example\n")
    
    example_basic_usage()
    
    logger.info("\n" + "="*50 + "\n")
    
    example_context_manager()
    
    logger.info("\n" + "="*50 + "\n")
    
    example_memory_management()