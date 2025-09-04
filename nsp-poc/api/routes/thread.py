from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from shared.mongodb_lib.client import MongoDBClient

router = APIRouter()

class ThreadTitleUpdate(BaseModel):
    title: str = Field(..., description="New title for the thread")


@router.get("/messages/{ogCode}/{thread_id}")
async def get_thread_messages_endpoint(ogCode: str, thread_id: str, og_key: str = Header(..., alias="OG_KEY")):
    """
    - 스레드 메시지 조회
    """
    with MongoDBClient() as client:
        if not client.organizations.verify_og_key(ogCode, og_key):
            raise HTTPException(status_code=401, detail="Invalid OG credentials")
        messages = client.messages.get_thread_messages(ogCode, thread_id)
        return {"messages": messages}


@router.get("/list/{ogCode}/{user_id}/{function}")
async def get_function_threads_with_titles(ogCode: str, user_id: str, function: str, og_key: str = Header(..., alias="OG_KEY")):
    """
    - 스레드 리스트 조회
    """
    with MongoDBClient() as client:
        if not client.organizations.verify_og_key(ogCode, og_key):
            raise HTTPException(status_code=401, detail="Invalid OG credentials")
        
        # Get user threads for the specific function
        thread_ids = client.threads.get_user_threads(ogCode, user_id, function)
        titles = []
        
        for thread_id in thread_ids:
            thread = client.threads.get_thread(ogCode, thread_id)
            if thread:
                titles.append({
                    "thread_id": thread_id,
                    "title": thread.get("title", ""),
                    "last_timestamp": thread.get("last_timestamp")
                })
        
        # Sort threads by most recent activity
        titles.sort(key=lambda x: x.get("last_timestamp", 0), reverse=True)
        return {"threads": titles}


@router.delete("/delete/{ogCode}/{user_id}/{thread_id}")
async def delete_thread_endpoint(ogCode: str, user_id: str, thread_id: str, og_key: str = Header(..., alias="OG_KEY")):
    """
    - user_thread 컬렉션에서도 참조를 제거합니다.
    """
    with MongoDBClient() as client:
        if not client.organizations.verify_og_key(ogCode, og_key):
            raise HTTPException(status_code=401, detail="Invalid OG credentials")
        
        # Get thread info to find function_name
        thread = client.threads.get_thread(ogCode, thread_id)
        if not thread:
            raise HTTPException(status_code=404, detail="Thread not found")
        
        function_name = thread.get("function_name")
        if function_name:
            client.threads.remove_user_thread(ogCode, user_id, function_name, thread_id)
        
        return {"detail": "Thread deleted successfully"}



@router.put("/title/{ogCode}/{user_id}/{thread_id}")
async def update_thread_title(
    ogCode: str,
    user_id: str,
    thread_id: str,
    payload: ThreadTitleUpdate,
    og_key: str = Header(..., alias="OG_KEY")
):
    """
    - 스레드 제목 업데이트
    """
    with MongoDBClient() as client:
        if not client.organizations.verify_og_key(ogCode, og_key):
            raise HTTPException(status_code=401, detail="Invalid OG credentials")
        
        # Verify thread exists and belongs to user
        thread = client.threads.get_thread(ogCode, thread_id)
        if not thread or thread.get("user_id") != user_id:
            raise HTTPException(status_code=404, detail="Thread not found")
        
        # Update thread title
        success = client.threads.update_thread_title(ogCode, thread_id, payload.title)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update thread title")
        
        return {"thread_id": thread_id, "title": payload.title}