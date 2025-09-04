# nsp-poc 리팩토링 요약 (기능 변경 없음)

## 중복 제거
- `generate_id`, `log_call` → **`shared/utils.py`**로 공용화
  - `shared/mongodb_lib/utils.py`, `shared/qdrant_lib/utils.py`는 공용 모듈을 **재사용(import)** 하도록 변경
- `get_mongodb_client` → **`shared/mongodb_lib/client.py`**에 싱글턴 접근자 추가
  - `api/routes/admin.py`, `api/routes/ai_assist.py`의 동일 함수 **삭제** 후 공용 함수 사용

## 디렉토리/파일 통합
- `postgres/` 디렉토리 **삭제**
  - `postgres/init.sql` → `shared/postgre_lib/init.sql`
  - `postgres/metadata_course.csv` → `shared/postgre_lib/metadata_course.csv`
  - `postgres/Dockerfile` → `docker/postgres.Dockerfile`

## 패키지 안정화
- `api/__init__.py`, `shared/__init__.py` 추가 (import 경로 명시화)

## 코드 가독성
- 변경된 파일 상단/임포트 라인에 “공용화” 주석 추가
- 클래스 메서드 `generate_id(self)`는 내부 구현을 공용 함수 호출로 치환(서명/반환 동일)

> 모든 변경은 **런타임 동작/인터페이스**에 영향을 주지 않도록 설계되었습니다.
