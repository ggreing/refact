"""공용 유틸리티 (기능 변경 없음)
- generate_id: 날짜+UUID 고유 ID
- log_call: 호출/예외 로깅 데코레이터
"""
from datetime import datetime
import uuid, logging
from functools import wraps

def generate_id() -> str:
    time_str = datetime.now().strftime('%Y%m%d%H%M%S')
    random_uuid = str(uuid.uuid4()).replace('-', '')
    return f"{time_str}-{random_uuid}"

def log_call(func):
    """로그를 남기고 함수를 실행하는 데코레이터."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        logging.info(f"Called {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            return func(*args, **kwargs)
        except Exception:
            logging.exception(f"Exception in {func.__name__}")
            raise
    return wrapper
