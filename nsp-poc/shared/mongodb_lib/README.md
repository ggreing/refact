# MongoDB Library for NSP Chatbot

깔끔하고 모듈화된 MongoDB 클라이언트 라이브러리입니다. 각 기능이 분리되어 있어 재사용성과 유지보수성이 높습니다.

## 주요 특징

- **모듈화된 구조**: 각 기능별로 매니저 클래스 분리
- **외부 의존성 최소화**: AI 그래프 등 외부 의존성 제거
- **타입 힌트 지원**: 모든 함수에 타입 힌트 적용
- **로깅 지원**: 자동 로깅 및 에러 추적
- **컨텍스트 매니저**: 자동 연결 관리 지원

## 설치

```bash
pip install pymongo python-dotenv
```

## 구조

```
mongodb_lib/
├── __init__.py          # 패키지 초기화
├── client.py            # 통합 클라이언트
├── config.py            # 설정 관리
├── models.py            # 데이터 모델
├── utils.py             # 유틸리티 함수
├── base_client.py       # 기본 MongoDB 클라이언트
├── organization_manager.py  # 조직 관리
├── user_manager.py      # 사용자 관리
├── thread_manager.py    # 스레드 관리
├── message_manager.py   # 메시지 관리
├── vectorstore_manager.py   # 벡터스토어 관리
├── memory_manager.py    # 메모리 관리
├── logging_manager.py   # 로깅 관리
├── example.py           # 사용 예제
└── README.md            # 이 파일
```

## 기본 사용법

### 1. 라이브러리 가져오기

```python
from mongodb_lib import MongoDBClient
```

### 2. 클라이언트 생성

```python
# 환경변수 MONGO_URI 사용
client = MongoDBClient()

# 또는 직접 URI 지정
client = MongoDBClient(mongo_uri="mongodb://localhost:27017")
```

### 3. 기본 작업

```python
# 조직 생성
client.organizations.create_og_entry("My Org", "my_org", "secret_key")

# 사용자 생성
client.users.create_user("my_org", "John Doe", "user123")

# 스레드 생성
thread_id = client.threads.add_user_thread("my_org", "user123", "chat", "general")

# 메시지 추가
msg_id = client.generate_id()
client.messages.add_user_message("my_org", thread_id, "general", msg_id, "Hello!")

# 연결 종료
client.close()
```

### 4. 컨텍스트 매니저 사용

```python
with MongoDBClient() as client:
    # 작업 수행
    client.users.create_user("my_org", "Jane Doe", "user456")
    # 자동으로 연결이 종료됨
```

## 매니저별 주요 기능

### OrganizationManager
- `create_og_entry()`: 조직 생성
- `get_og_entry()`: 조직 조회
- `verify_og_key()`: 키 검증
- `update_og_key()`: 키 업데이트

### UserManager
- `create_user()`: 사용자 생성
- `get_user()`: 사용자 조회
- `update_user()`: 사용자 정보 업데이트
- `delete_user()`: 사용자 삭제

### ThreadManager
- `add_user_thread()`: 스레드 생성
- `get_user_threads()`: 사용자 스레드 목록 조회
- `check_user_thread()`: 스레드 존재 확인
- `update_thread_title()`: 스레드 제목 업데이트

### MessageManager
- `add_user_message()`: 사용자 메시지 추가
- `add_ai_message()`: AI 메시지 추가
- `add_system_message()`: 시스템 메시지 추가
- `get_history()`: 메시지 히스토리 조회

### VectorstoreManager
- `add_vectorstore()`: 벡터스토어 항목 추가
- `get_vectorstore_entry()`: 벡터스토어 항목 조회
- `set_thread_vectorstore()`: 스레드에 벡터스토어 연결
- `get_thread_vectorstore()`: 스레드 벡터스토어 조회

### MemoryManager
- `get_memory()`: 장기 메모리 조회
- `save_long_term_memory()`: 장기 메모리 저장
- `create_memory_entry()`: 메모리 엔트리 생성
- `analyze_message_tokens()`: 메시지 토큰 분석

### LoggingManager
- `log_ai_response()`: AI 응답 로그
- `log_error()`: 에러 로그
- `log_user_activity()`: 사용자 활동 로그
- `get_ai_logs()`: AI 로그 조회

## 환경 설정

`.env` 파일에 MongoDB URI를 설정하세요:

```env
MONGO_URI=mongodb://username:password@localhost:27017/database_name
```

## 예제 실행

```bash
python example.py
```


## 마이그레이션 가이드

기존 `mongo_db_client.py`에서 새 라이브러리로 마이그레이션:

### Before (기존 코드)
```python
from mongo_db_client import create_user, get_user
create_user("org_code", "John", "user123")
user = get_user("org_code", "user123")
```

### After (새 라이브러리)
```python
from mongodb_lib import MongoDBClient
client = MongoDBClient()
client.users.create_user("org_code", "John", "user123")
user = client.users.get_user("org_code", "user123")
client.close()
```

## 개발

새로운 기능 추가 시:

1. 해당 매니저 클래스에 메서드 추가
2. 필요한 경우 새 매니저 클래스 생성
3. `client.py`에서 새 매니저를 통합
4. `__init__.py`에서 export 추가
5. 예제와 문서 업데이트

## 주의사항

- 모든 연결은 사용 후 `close()` 호출 필요
- 컨텍스트 매니저 사용 권장
- 로그 파일은 `log/mongo_log.log`에 생성됨
- 환경변수 `MONGO_URI` 필수 설정