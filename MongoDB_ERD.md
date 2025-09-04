# MongoDB ERD - NSP Chatbot System

이 문서는 NSP Chatbot 시스템의 MongoDB 데이터베이스 구조를 Mermaid ERD로 표현합니다.

## 시스템 개요

MongoDB는 조직(Organization) 기반으로 데이터베이스를 분리하며, 각 조직별로 독립적인 컬렉션들을 관리합니다.

## ERD 다이어그램

```mermaid
erDiagram
    %% 전역 컬렉션 (og_keys 데이터베이스)
    OG_KEYS {
        string name "조직명"
        string code "조직코드 (PK)"
        string key "액세스 키"
        datetime created_at "생성일시"
        datetime updated_at "수정일시"
    }

    %% 조직별 컬렉션들 (각 조직코드별 데이터베이스)
    USER {
        string _id "사용자 ID (PK)"
        string name "사용자명"
        datetime created_at "생성일시"
        datetime updated_at "수정일시"
    }

    USER_THREAD {
        string user_id "사용자 ID (PK)"
        array threads "스레드 배열"
        string function_name "기능명"
        array thread "스레드 ID 배열"
    }

    THREADS {
        string _id "스레드 ID (PK)"
        string user_id "사용자 ID"
        string function_name "기능명"
        string title "스레드 제목 (nullable)"
        array messages "메시지 배열"
        array long_term_memory "장기 메모리 배열"
        string vectorstore "벡터스토어 ID (nullable)"
        datetime create_timestamp "생성일시"
        datetime last_timestamp "마지막 수정일시"
    }

    MESSAGES {
        string msg_id "메시지 ID (PK)"
        string role "역할 (user/ai/system)"
        any content "메시지 내용 (text 또는 object)"
        datetime timestamp "타임스탬프"
    }

    LONG_TERM_MEMORY {
        string msg_id "메모리 ID (PK)"
        string memory "메모리 내용"
        datetime replace_timestamp "대체 타임스탬프 (nullable)"
        datetime timestamp "생성일시"
    }

    VECTORSTORE {
        string _id "벡터스토어 ID (PK)"
        array files "파일 정보 배열"
        object metadata "메타데이터"
        datetime created_at "생성일시"
        datetime updated_at "수정일시"
    }

    VECTORSTORE_FILES {
        string filename "파일명"
        string file_hash "파일 해시"
        number file_size "파일 크기"
        datetime uploaded_at "업로드일시"
    }

    ERROR_LOG {
        object error_data "에러 데이터"
        datetime timestamp "에러일시"
    }


    %% 관계 정의
    OG_KEYS ||--o{ USER : "조직별 사용자 관리"
    OG_KEYS ||--o{ THREADS : "조직별 스레드 관리"
    OG_KEYS ||--o{ VECTORSTORE : "조직별 벡터스토어 관리"
    OG_KEYS ||--o{ ERROR_LOG : "조직별 에러 로그"
    
    USER ||--o{ USER_THREAD : "사용자별 스레드 매핑"
    USER ||--o{ THREADS : "사용자가 생성한 스레드"
    
    USER_THREAD ||--o{ THREADS : "스레드 매핑"
    
    THREADS ||--o{ MESSAGES : "메시지 포함 (embedded)"
    THREADS ||--o{ LONG_TERM_MEMORY : "장기 메모리 포함 (embedded)"
    THREADS }o--|| VECTORSTORE : "벡터스토어 참조"
    
    VECTORSTORE ||--o{ VECTORSTORE_FILES : "파일 정보 포함 (embedded)"
```

## 컬렉션 상세 설명

### 1. 전역 컬렉션

#### og_keys.og_keys
- **목적**: 조직 인증 정보 관리
- **특징**: 모든 조직의 액세스 키를 중앙 관리
- **보안**: 조직별 접근 권한 제어

### 2. 조직별 컬렉션 (각 조직코드별 데이터베이스)

#### user
- **목적**: 조직 내 사용자 관리
- **특징**: 간단한 사용자 정보만 저장

#### user_thread
- **목적**: 사용자와 스레드 간 매핑 관리
- **특징**: 사용자별 기능별 스레드 목록을 배열로 관리

#### threads
- **목적**: 채팅 스레드 및 대화 컨텍스트 관리
- **특징**: 
  - 메시지와 장기 메모리를 직접 임베디드
  - 단일 기능별 스레드 관리
  - 벡터스토어 참조 가능 (nullable)
  - 제목은 선택적 (처음에는 null, 후에 업데이트 가능)

#### vectorstore
- **목적**: RAG를 위한 벡터 데이터 관리
- **특징**: 
  - 파일 정보를 배열로 임베디드
  - 메타데이터 지원

### 3. 로그 컬렉션

#### error_log
- **목적**: 시스템 에러 추적


## 데이터 구조 특징

### 1. 멀티테넌트 아키텍처
- 조직별 완전 분리된 데이터베이스
- og_keys를 통한 중앙 인증 관리

### 2. 임베디드 vs 참조
- **임베디드**: messages, long_term_memory, files (강한 관계)
- **참조**: vectorstore (약한 관계, 재사용 가능, nullable)

### 3. 단순화된 구조
- **서브펑션 제거**: 스레드당 하나의 기능만 관리
- **AI 로그 제거**: 시스템 로그를 최소화하여 성능 향상

### 4. 타임스탬프 관리
- 생성, 수정, 마지막 접근 시간 추적
- 로그 데이터의 시간 기반 쿼리 최적화

### 5. 유연한 스키마
- 메시지 content: Any 타입으로 text 또는 object 형태 지원
- 메타데이터: 확장 가능한 구조
- Nullable 필드들: title, vectorstore, replace_timestamp

## 성능 고려사항

### 인덱스 권장사항
```javascript
// user_thread 컬렉션
db.user_thread.createIndex({ "user_id": 1 })

// threads 컬렉션
db.threads.createIndex({ "user_id": 1, "function_name": 1 })
db.threads.createIndex({ "last_timestamp": -1 })

// 로그 컬렉션들
db.error_log.createIndex({ "timestamp": -1 })
```

### 데이터 라이프사이클
- 에러 로그: 30일 자동 삭제 (설정 가능)
- 스레드 데이터: 사용자 관리
- 벡터스토어: 명시적 삭제