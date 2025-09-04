"""
MinIO 스토리지 라이브러리 - 통합 파일
"""
import os
from minio import Minio
from minio.error import S3Error
from datetime import timedelta
from typing import Optional, List, Union, BinaryIO
from pathlib import Path
from dataclasses import dataclass
import io
import uuid
import mimetypes
import logging

logger = logging.getLogger(__name__)


@dataclass
class MinIOConfig:
    """MinIO 연결 및 버킷 설정"""
    
    # 연결 설정
    endpoint: str
    access_key: str
    secret_key: str
    secure: bool = False
    
    # 버킷 설정
    bucket_name: str = "base-chat"
    
    # 업로드 설정
    max_file_size: int = 100 * 1024 * 1024  # 100MB
    allowed_extensions: list = None
    
    def __post_init__(self):
        if self.allowed_extensions is None:
            self.allowed_extensions = [
                # 이미지
                '.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg',
                # 문서
                '.pdf', '.doc', '.docx', '.txt', '.md', '.rtf',
                # 스프레드시트
                '.xls', '.xlsx', '.csv',
                # 프레젠테이션
                '.ppt', '.pptx',
                # 압축파일
                '.zip', '.rar', '.7z',
                # 기타
                '.json', '.xml', '.yaml', '.yml'
            ]
    
    @property
    def max_file_size_mb(self) -> float:
        """파일 사이즈를 MB로 반환"""
        return self.max_file_size / (1024 * 1024)


def get_minio_config() -> MinIOConfig:
    """환경변수에서 MinIO 설정을 로드"""
    return MinIOConfig(
        endpoint=os.getenv("MINIO_ENDPOINT", "localhost:9000"),
        access_key=os.getenv("MINIO_ROOT_USER", "minioadmin"),
        secret_key=os.getenv("MINIO_ROOT_PASSWORD", "minioadmin"),
        secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
        bucket_name=os.getenv("MINIO_BUCKET", "base-chat"),
        max_file_size=int(os.getenv("MINIO_MAX_FILE_SIZE", str(100 * 1024 * 1024)))
    )


class MinIOClient:
    """통합 MinIO 클라이언트"""
    
    def __init__(self, config: Optional[MinIOConfig] = None):
        self.config = config or get_minio_config()
        self._client: Optional[Minio] = None
    
    @property
    def client(self) -> Minio:
        """MinIO 클라이언트 인스턴스 (지연 초기화)"""
        if self._client is None:
            self._client = Minio(
                self.config.endpoint,
                access_key=self.config.access_key,
                secret_key=self.config.secret_key,
                secure=self.config.secure,
            )
            self._ensure_bucket_exists()
        return self._client
    
    def _ensure_bucket_exists(self):
        """버킷 존재 확인 및 생성"""
        try:
            if not self.client.bucket_exists(self.config.bucket_name):
                self.client.make_bucket(self.config.bucket_name)
                logger.info(f"Created bucket: {self.config.bucket_name}")
        except S3Error as e:
            logger.error(f"Failed to create bucket: {e}")
            raise
    
    def _generate_object_name(self, original_filename: str, prefix: str = "") -> str:
        """고유한 객체 이름 생성"""
        file_ext = Path(original_filename).suffix.lower()
        unique_id = str(uuid.uuid4())
        
        if prefix:
            return f"{prefix}/{unique_id}{file_ext}"
        return f"{unique_id}{file_ext}"
    
    def _validate_file_size(self, data: Union[bytes, BinaryIO]) -> bool:
        """파일 크기 검증"""
        if isinstance(data, bytes):
            size = len(data)
        else:
            current_pos = data.tell()
            data.seek(0, 2)  # EOF로 이동
            size = data.tell()
            data.seek(current_pos)  # 원래 위치로 복원
        
        return size <= self.config.max_file_size
    
    def _validate_file_extension(self, filename: str) -> bool:
        """파일 확장자 검증"""
        file_ext = Path(filename).suffix.lower()
        return file_ext in self.config.allowed_extensions
    
    def put_object_bytes(
        self, 
        object_name: str, 
        data: bytes, 
        content_type: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> str:
        """바이트 데이터를 객체로 업로드"""
        if not self._validate_file_size(data):
            raise ValueError(f"File size exceeds maximum allowed size ({self.config.max_file_size_mb}MB)")
        
        if content_type is None:
            content_type = mimetypes.guess_type(object_name)[0] or "application/octet-stream"
        
        data_stream = io.BytesIO(data)
        
        try:
            self.client.put_object(
                self.config.bucket_name,
                object_name,
                data_stream,
                length=len(data),
                content_type=content_type,
                metadata=metadata or {}
            )
            logger.info(f"Successfully uploaded object: {object_name}")
            return f"{self.config.bucket_name}/{object_name}"
            
        except S3Error as e:
            logger.error(f"Failed to upload object {object_name}: {e}")
            raise
    
    def get_object_bytes(self, object_name: str) -> bytes:
        """객체를 바이트로 다운로드"""
        try:
            response = self.client.get_object(self.config.bucket_name, object_name)
            try:
                data = response.read()
                logger.info(f"Successfully downloaded object: {object_name}")
                return data
            finally:
                response.close()
                response.release_conn()
                
        except S3Error as e:
            logger.error(f"Failed to download object {object_name}: {e}")
            raise
    
    def upload_file(
        self, 
        file_path: Union[str, Path], 
        object_name: Optional[str] = None,
        prefix: str = ""
    ) -> str:
        """파일 업로드"""
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        if not self._validate_file_extension(file_path.name):
            raise ValueError(f"File extension not allowed: {file_path.suffix}")
        
        if object_name is None:
            object_name = self._generate_object_name(file_path.name, prefix)
        
        content_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        
        try:
            self.client.fput_object(
                self.config.bucket_name,
                object_name,
                str(file_path),
                content_type=content_type
            )
            logger.info(f"Successfully uploaded file: {file_path} -> {object_name}")
            return f"{self.config.bucket_name}/{object_name}"
            
        except S3Error as e:
            logger.error(f"Failed to upload file {file_path}: {e}")
            raise
    
    def download_file(self, object_name: str, file_path: Union[str, Path]) -> Path:
        """파일 다운로드"""
        file_path = Path(file_path)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            self.client.fget_object(
                self.config.bucket_name,
                object_name,
                str(file_path)
            )
            logger.info(f"Successfully downloaded file: {object_name} -> {file_path}")
            return file_path
            
        except S3Error as e:
            logger.error(f"Failed to download file {object_name}: {e}")
            raise
    
    def presigned_get_url(
        self, 
        object_name: str, 
        expires_seconds: int = 3600
    ) -> str:
        """Presigned GET URL 생성"""
        try:
            url = self.client.presigned_get_object(
                self.config.bucket_name,
                object_name,
                expires=timedelta(seconds=expires_seconds),
            )
            logger.info(f"Generated presigned URL for {object_name} (expires in {expires_seconds}s)")
            return url
            
        except S3Error as e:
            logger.error(f"Failed to generate presigned URL for {object_name}: {e}")
            raise
    
    def presigned_put_url(
        self,
        object_name: str,
        expires_seconds: int = 3600
    ) -> str:
        """Presigned PUT URL 생성 (직접 업로드용)"""
        try:
            url = self.client.presigned_put_object(
                self.config.bucket_name,
                object_name,
                expires=timedelta(seconds=expires_seconds),
            )
            logger.info(f"Generated presigned PUT URL for {object_name}")
            return url
            
        except S3Error as e:
            logger.error(f"Failed to generate presigned PUT URL for {object_name}: {e}")
            raise
    
    def delete_object(self, object_name: str) -> bool:
        """객체 삭제"""
        try:
            self.client.remove_object(self.config.bucket_name, object_name)
            logger.info(f"Successfully deleted object: {object_name}")
            return True
            
        except S3Error as e:
            logger.error(f"Failed to delete object {object_name}: {e}")
            return False
    
    def list_objects(self, prefix: str = "", recursive: bool = True) -> List[str]:
        """객체 목록 조회"""
        try:
            objects = self.client.list_objects(
                self.config.bucket_name,
                prefix=prefix,
                recursive=recursive
            )
            object_names = [obj.object_name for obj in objects]
            logger.info(f"Listed {len(object_names)} objects with prefix: {prefix}")
            return object_names
            
        except S3Error as e:
            logger.error(f"Failed to list objects: {e}")
            raise
    
    def object_exists(self, object_name: str) -> bool:
        """객체 존재 여부 확인"""
        try:
            self.client.stat_object(self.config.bucket_name, object_name)
            return True
        except S3Error:
            return False


# 전역 클라이언트 인스턴스
_global_client: Optional[MinIOClient] = None


def get_minio_client(config: Optional[MinIOConfig] = None) -> MinIOClient:
    """전역 MinIO 클라이언트 반환"""
    global _global_client
    if _global_client is None:
        _global_client = MinIOClient(config)
    return _global_client


# 편의 함수들
def put_object_bytes(
    object_name: str, 
    data: bytes, 
    content_type: str = "application/octet-stream"
) -> str:
    """바이트 데이터 업로드 (편의 함수)"""
    client = get_minio_client()
    return client.put_object_bytes(object_name, data, content_type)


def get_object_bytes(object_name: str) -> bytes:
    """객체 다운로드 (편의 함수)"""
    client = get_minio_client()
    return client.get_object_bytes(object_name)


def presigned_get_url(object_name: str, expires_seconds: int = 3600) -> str:
    """Presigned URL 생성 (편의 함수)"""
    client = get_minio_client()
    return client.presigned_get_url(object_name, expires_seconds)


def delete_object(object_name: str) -> bool:
    """객체 삭제 (편의 함수)"""
    client = get_minio_client()
    return client.delete_object(object_name)


def list_objects(prefix: str = "") -> List[str]:
    """객체 목록 (편의 함수)"""
    client = get_minio_client()
    return client.list_objects(prefix)


def upload_file(file_path: Union[str, Path], prefix: str = "") -> str:
    """파일 업로드 (편의 함수)"""
    client = get_minio_client()
    return client.upload_file(file_path, prefix=prefix)


def download_file(object_name: str, file_path: Union[str, Path]) -> Path:
    """파일 다운로드 (편의 함수)"""
    client = get_minio_client()
    return client.download_file(object_name, file_path)