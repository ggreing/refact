from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
import uuid
import os
import sys

# MongoDB 클라이언트 설정
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from shared.mongodb_lib import MongoDBClient
from shared.mongodb_lib.client import get_mongodb_client  # 중앙화된 클라이언트 사용


# MongoDB 클라이언트 지연 초기화
mdb = None


router = APIRouter()


def generate_id() -> str:
    """
    현재 시간과 UUID를 조합해 고유한 메시지 ID 생성.
    """
    time_str = datetime.now().strftime("%Y%m%d%H%M%S")
    random_uuid = str(uuid.uuid4()).replace("-", "")
    return f"{time_str}-{random_uuid}"


# -------------------
# OG 키 생성용 모델 및 엔드포인트
# -------------------

class OGKeyRequest(BaseModel):
    ogName: str = Field(..., description="기관 이름")
    ogCode: str = Field(..., description="기관 코드")

class OGKeyResponse(BaseModel):
    ogName: str = Field(..., description="기관 이름")
    ogCode: str = Field(..., description="기관 코드")
    ogKey: str = Field(..., description="생성된 OG 키")
    createdAt: str = Field(..., description="생성 시간")
    updatedAt: str = Field(..., description="수정 시간")

class OGKeyUpdateRequest(BaseModel):
    ogName: Optional[str] = Field(None, description="기관 이름")
    ogKey: Optional[str] = Field(None, description="새로운 OG 키")

class OGKeyListResponse(BaseModel):
    total: int = Field(..., description="전체 개수")
    ogKeys: List[OGKeyResponse] = Field(..., description="OG 키 목록")


@router.post(
    "/og/key",
    response_model=OGKeyResponse,
    summary="OG 엔트리 생성",
    description="주어진 ogName과 ogCode로 새로운 OG 엔트리를 생성하고 키를 반환합니다. 이미 존재하면 400 에러를 반환합니다."
)
async def create_og_key(request: OGKeyRequest):
    client = get_mongodb_client()
    
    # 이미 같은 ogCode가 있는지 확인
    existing = client.organizations.get_og_entry(request.ogCode)
    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"OG 코드 `{request.ogCode}`가 이미 존재합니다."
        )
    # 새 키 생성 (UUID)
    new_key = uuid.uuid4().hex
    # DB에 저장 (create_og_entry 사용)
    try:
        client.organizations.create_og_entry(request.ogName, request.ogCode, new_key)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OG 엔트리 생성 중 오류 발생: {e}"
        )
    
    # 생성된 엔트리 조회하여 반환
    created_entry = client.organizations.get_og_entry(request.ogCode)
    return OGKeyResponse(
        ogName=created_entry["name"],
        ogCode=created_entry["code"], 
        ogKey=created_entry["key"],
        createdAt=created_entry["created_at"].isoformat() if created_entry.get("created_at") else "",
        updatedAt=created_entry["updated_at"].isoformat() if created_entry.get("updated_at") else ""
    )


@router.get(
    "/og/keys",
    response_model=OGKeyListResponse,
    summary="OG 키 목록 조회",
    description="등록된 모든 OG 키 목록을 반환합니다."
)
async def get_og_keys():
    client = get_mongodb_client()
    
    try:
        # MongoDB에서 모든 OG 엔트리 조회
        og_entries = list(client.organizations.og_keys_collection.find({}))
        
        og_keys = []
        for entry in og_entries:
            og_keys.append(OGKeyResponse(
                ogName=entry["name"],
                ogCode=entry["code"],
                ogKey=entry["key"],
                createdAt=entry["created_at"].isoformat() if entry.get("created_at") else "",
                updatedAt=entry["updated_at"].isoformat() if entry.get("updated_at") else ""
            ))
        
        return OGKeyListResponse(total=len(og_keys), ogKeys=og_keys)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OG 키 목록 조회 중 오류 발생: {e}"
        )


@router.get(
    "/og/key/{og_code}",
    response_model=OGKeyResponse,
    summary="특정 OG 키 조회",
    description="특정 기관 코드의 OG 키 정보를 반환합니다."
)
async def get_og_key(og_code: str):
    client = get_mongodb_client()
    
    og_entry = client.organizations.get_og_entry(og_code)
    if not og_entry:
        raise HTTPException(
            status_code=404,
            detail=f"OG 코드 `{og_code}`를 찾을 수 없습니다."
        )
    
    return OGKeyResponse(
        ogName=og_entry["name"],
        ogCode=og_entry["code"],
        ogKey=og_entry["key"],
        createdAt=og_entry["created_at"].isoformat() if og_entry.get("created_at") else "",
        updatedAt=og_entry["updated_at"].isoformat() if og_entry.get("updated_at") else ""
    )


@router.put(
    "/og/key/{og_code}",
    response_model=OGKeyResponse,
    summary="OG 키 정보 수정",
    description="기관의 이름이나 키를 수정합니다."
)
async def update_og_key(og_code: str, request: OGKeyUpdateRequest):
    client = get_mongodb_client()
    
    # 기존 엔트리 확인
    existing = client.organizations.get_og_entry(og_code)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"OG 코드 `{og_code}`를 찾을 수 없습니다."
        )
    
    try:
        # 수정할 필드 준비
        update_fields = {"updated_at": datetime.now()}
        
        if request.ogName is not None:
            update_fields["name"] = request.ogName
            
        if request.ogKey is not None:
            update_fields["key"] = request.ogKey
        
        # MongoDB 업데이트
        result = client.organizations.og_keys_collection.update_one(
            {"code": og_code},
            {"$set": update_fields}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=500,
                detail="OG 키 수정에 실패했습니다."
            )
        
        # 수정된 엔트리 반환
        updated_entry = client.organizations.get_og_entry(og_code)
        return OGKeyResponse(
            ogName=updated_entry["name"],
            ogCode=updated_entry["code"],
            ogKey=updated_entry["key"],
            createdAt=updated_entry["created_at"].isoformat() if updated_entry.get("created_at") else "",
            updatedAt=updated_entry["updated_at"].isoformat() if updated_entry.get("updated_at") else ""
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OG 키 수정 중 오류 발생: {e}"
        )


@router.delete(
    "/og/key/{og_code}",
    summary="OG 키 삭제",
    description="특정 기관의 OG 키를 삭제합니다."
)
async def delete_og_key(og_code: str):
    client = get_mongodb_client()
    
    # 기존 엔트리 확인
    existing = client.organizations.get_og_entry(og_code)
    if not existing:
        raise HTTPException(
            status_code=404,
            detail=f"OG 코드 `{og_code}`를 찾을 수 없습니다."
        )
    
    try:
        success = client.organizations.delete_og_entry(og_code)
        if not success:
            raise HTTPException(
                status_code=500,
                detail="OG 키 삭제에 실패했습니다."
            )
        
        return {"message": f"OG 코드 `{og_code}`가 성공적으로 삭제되었습니다."}
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OG 키 삭제 중 오류 발생: {e}"
        )


@router.post(
    "/og/key/{og_code}/verify",
    summary="OG 키 검증",
    description="제공된 키가 올바른지 검증합니다."
)
async def verify_og_key(og_code: str, og_key: str = Header(..., description="검증할 OG 키")):
    client = get_mongodb_client()
    
    try:
        is_valid = client.organizations.verify_og_key(og_code, og_key)
        return {
            "valid": is_valid,
            "message": "키가 유효합니다." if is_valid else "키가 유효하지 않습니다."
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OG 키 검증 중 오류 발생: {e}"
        )