"""
MongoDB Library 사용 예제

이 파일은 MongoDB 라이브러리의 기본 사용법을 보여줍니다.
"""

from mongodb_lib import MongoDBClient


def example_basic_usage():
    """기본 사용법 예제"""
    
    # MongoDB 클라이언트 생성
    client = MongoDBClient()
    
    try:
        # 1. 조직 관리
        print("=== Organization Management ===")
        org_name = "Example Organization"
        org_code = "example_org"
        org_key = "example_key_123"
        
        # 조직 생성
        client.organizations.create_og_entry(org_name, org_code, org_key)
        
        # 조직 조회
        org_entry = client.organizations.get_og_entry(org_code)
        print(f"Organization: {org_entry}")
        
        # 키 검증
        is_valid = client.organizations.verify_og_key(org_code, org_key)
        print(f"Key valid: {is_valid}")
        
        # 2. 사용자 관리
        print("\n=== User Management ===")
        user_id = "user_123"
        user_name = "John Doe"
        
        # 사용자 생성
        client.users.create_user(org_code, user_name, user_id)
        
        # 사용자 조회
        user = client.users.get_user(org_code, user_id)
        print(f"User: {user}")
        
        # 3. 스레드 관리
        print("\n=== Thread Management ===")
        function_name = "chat_function"
        
        # 스레드 생성 (sub_function 제거)
        thread_id = client.threads.add_user_thread(org_code, user_id, function_name)
        print(f"Created thread: {thread_id}")
        
        # 사용자 스레드 조회
        threads = client.threads.get_user_threads(org_code, user_id, function_name)
        print(f"User threads: {threads}")
        
        # 4. 메시지 관리 (sub_function 제거)
        print("\n=== Message Management ===")
        msg_id = client.generate_id()
        
        # 사용자 메시지 추가
        client.messages.add_user_message(org_code, thread_id, msg_id, "Hello, AI!")
        
        # AI 메시지 추가
        ai_msg_id = client.generate_id()
        client.messages.add_ai_message(org_code, thread_id, ai_msg_id, "Hello! How can I help you?")
        
        # 메시지 히스토리 조회
        history = client.messages.get_history(org_code, thread_id)
        print(f"Message history: {history}")
        
        # 5. 벡터스토어 관리
        print("\n=== Vectorstore Management ===")
        vector_id = "vector_123"
        files = [
            {
                "filename": "document1.pdf",
                "file_hash": "abc123",
                "file_size": 1024,
                "uploaded_at": client.config.current_time
            }
        ]
        
        # 벡터스토어 항목 추가
        client.vectorstore.add_vectorstore(org_code, vector_id, files)
        
        # 스레드에 벡터스토어 연결 (sub_function 제거)
        client.vectorstore.set_thread_vectorstore(org_code, thread_id, vector_id)
        
        # 6. 로깅 (AI 로그 제거)
        print("\n=== Logging ===")
        
        # 사용자 활동 로그
        client.logging.log_user_activity(org_code, user_id, "chat_started", {"thread_id": thread_id})
        
        # 에러 로그
        error_data = {
            "error_type": "validation_error",
            "message": "Invalid input format",
            "user_id": user_id
        }
        client.logging.log_error(org_code, error_data)
        
        # 로그 조회
        recent_activities = client.logging.get_user_activities(org_code, user_id, limit=5)
        print(f"Recent activities count: {len(recent_activities)}")
        
        error_logs = client.logging.get_error_logs(org_code, limit=5)
        print(f"Recent errors count: {len(error_logs)}")
        
        print("\n=== Example completed successfully ===")
        
    except Exception as e:
        print(f"Error occurred: {e}")
    
    finally:
        # 연결 종료
        client.close()


def example_context_manager():
    """컨텍스트 매니저 사용 예제"""
    
    with MongoDBClient() as client:
        org_code = "test_org"
        
        # 조직 생성
        client.organizations.create_og_entry("Test Org", org_code, "test_key")
        
        # 사용자 생성
        client.users.create_user(org_code, "Test User", "test_user")
        
        print("Context manager example completed")


def example_memory_management():
    """메모리 관리 예제"""
    
    with MongoDBClient() as client:
        org_code = "memory_test_org"
        user_id = "memory_user"
        
        # 조직 및 사용자 설정
        client.organizations.create_og_entry("Memory Test Org", org_code, "memory_key")
        client.users.create_user(org_code, "Memory User", user_id)
        
        # 스레드 생성
        thread_id = client.threads.add_user_thread(org_code, user_id, "memory_chat")
        
        # 메시지 추가
        for i in range(5):
            user_msg_id = client.generate_id()
            ai_msg_id = client.generate_id()
            
            client.messages.add_user_message(org_code, thread_id, user_msg_id, f"User message {i}")
            client.messages.add_ai_message(org_code, thread_id, ai_msg_id, f"AI response {i}")
        
        # 메모리 관리
        messages = client.messages.get_thread_messages(org_code, thread_id)
        should_create = client.memory.should_create_memory(messages, trigger_token=50)
        print(f"Should create memory: {should_create}")
        
        if should_create:
            # 메모리 엔트리 생성
            memory_entry = client.memory.create_memory_entry("Summary of conversation about topics 1-5")
            client.memory.save_long_term_memory(org_code, thread_id, memory_entry)
            
            # 메모리 조회
            memories = client.memory.get_long_term_memories(org_code, thread_id)
            print(f"Long term memories: {len(memories)}")
            
            # 전체 메모리 히스토리 조회
            full_history = client.memory.get_memory(org_code, thread_id)
            print(f"Full history with memory: {len(full_history)} items")
        
        print("Memory management example completed")


if __name__ == "__main__":
    print("MongoDB Library Example\n")
    
    # 기본 사용법
    example_basic_usage()
    
    print("\n" + "="*50 + "\n")
    
    # 컨텍스트 매니저 사용법
    example_context_manager()
    
    print("\n" + "="*50 + "\n")
    
    # 메모리 관리 예제
    example_memory_management()