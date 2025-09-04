from fastapi import APIRouter, HTTPException, Header, Body, Depends
from fastapi.responses import StreamingResponse
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
import os
import json
import asyncio
import logging
from fastapi import UploadFile, File, Form
from pydantic import BaseModel, Field
from fastapi.encoders import jsonable_encoder

from api.services.chat_service import chat_service
from api.schemas.chat import ChatRequest, ChatResponse
from shared.mongodb_lib import MongoDBClient
import aio_pika
from shared.rabbitmq_lib.publisher import BasePublisher, TaskPublisher
from shared.rabbitmq_lib.consumer import BaseConsumer, TaskConsumer
from shared.mongodb_lib.client import get_mongodb_client  # 중앙화된 클라이언트 사용


router = APIRouter()
logger = logging.getLogger(__name__)

# MongoDB 클라이언트 지연 초기화
mdb = None


# 기관 인증 함수
async def verify_organization(og_code: str = Header(...), og_key: str = Header(...)):
    """기관 인증 검증"""
    try:
        mongodb_client = get_mongodb_client()
        
        # OrganizationManager의 verify_og_key 메서드 사용
        is_valid = mongodb_client.organizations.verify_og_key(og_code, og_key)
        
        if not is_valid:
            raise HTTPException(
                status_code=401, 
                detail="Invalid organization credentials"
            )
        
        # 기관 정보 반환
        org = mongodb_client.organizations.get_og_entry(og_code)
        if not org:
            raise HTTPException(
                status_code=401, 
                detail="Organization not found"
            )
        
        return org
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Organization verification failed: {str(e)}"
        )


class ContentData(BaseModel):
    """Content data schema"""
    text: str = Field(..., description="텍스트 내용")
    model: Optional[str] = Field(None, description="AI 모델 이름")

class AIAssistStreamRequest(BaseModel):
    """AI Assist stream request schema"""
    user_id: str = Field(..., description="사용자 ID")
    thread_id: Optional[str] = Field(None, description="스레드 ID (선택사항)")
    content: ContentData = Field(..., description="콘텐츠 정보")

class AIAssistRequest(BaseModel):
    """AI Assist request schema"""
    user_id: str = Field(..., description="사용자 ID")
    thread_id: Optional[str] = Field(None, description="스레드 ID (선택사항)")
    task_type: str = Field(..., description="AI 작업 유형 (code_review, documentation, debugging, optimization)")
    content: str = Field(..., description="작업 대상 콘텐츠")
    context: Optional[Dict[str, Any]] = Field(None, description="추가 컨텍스트 정보")
    parameters: Optional[Dict[str, Any]] = Field(None, description="작업별 매개변수")


@router.post("/ai_assist/stream")
async def ai_assist_stream(
    request: AIAssistStreamRequest,
    organization: dict = Depends(verify_organization)
):
    """AI 어시스턴트 SSE 스트림 API"""
    
    try:
        # MongoDB 클라이언트 및 ID 생성
        mongodb_client = get_mongodb_client()
        stream_id = str(uuid.uuid4())
        message_id = mongodb_client.generate_id()
        
        # Thread ID가 없으면 새로 생성
        if not request.thread_id:
            request.thread_id = mongodb_client.threads.add_user_thread(
                organization["code"], 
                request.user_id, 
                "ai_assist"
            )
        
        # 사용자 메시지 저장
        mongodb_client.messages.add_user_message(
            organization["code"],
            request.thread_id,
            message_id,
            {
                "text": request.content.text,
                "model": request.content.model,
                "stream_id": stream_id,
                "message_type": "ai_assist_request"
            }
        )
        
        # RabbitMQ에 요청 발행
        publisher = TaskPublisher()
        
        message_data = {
            "stream_id": stream_id,
            "message_id": message_id,
            "user_id": request.user_id,
            "thread_id": request.thread_id,
            "text": request.content.text,
            "model": request.content.model,
            "organization_code": organization["code"],
            "organization_id": str(organization.get("_id", organization["code"])),  # ObjectId 등 비JSON 타입을 문자열로 변환
            "timestamp": datetime.now().isoformat()
        }
        
        await publisher.publish_task("assist.request", message_data)
        await publisher.close()
        
        # SSE 스트림 생성
        async def generate_stream():
            # 큐에 메시지를 발행했음을 즉시 SSE로 전송
            queue_payload = {
                "type": "queue",
                "content": {"step": "start", "text": "Message sent to queue"},
                "thread_id": request.thread_id,
                "stream_id": stream_id
            }
            yield f"data: {json.dumps(jsonable_encoder(queue_payload), ensure_ascii=False)}\n\n"
            
            consumer = TaskConsumer()
            try:
                # 결과 소비 콜백
                result_data = []
                aggregated = []
                
                async def result_callback(payload: dict):
                    if payload.get("stream_id") == stream_id:
                        result_data.append(payload)
                
                # 타임아웃 설정 (30초)
                timeout = 30
                start_time = asyncio.get_event_loop().time()
                
                
                # 비동기적으로 결과 소비 시작
                consume_task = asyncio.create_task(
                    consumer.consume_results(
                        f"assist.response.{stream_id}", 
                        result_callback, 
                        timeout=timeout
                    )
                )
                
                # 결과를 스트리밍
                while True:
                    try:
                        # 타임아웃 체크
                        if asyncio.get_event_loop().time() - start_time > timeout:
                            yield f"data: {json.dumps(jsonable_encoder({'type': 'error', 'content': {'step': 'timeout', 'text': 'Stream timeout'}, 'thread_id': request.thread_id, 'stream_id': stream_id}), ensure_ascii=False)}\n\n"
                            break
                        
                        # 새로운 데이터가 있는지 확인
                        if result_data:
                            data = result_data.pop(0)
                            logger.debug(f"Received data from queue: {data}")
                            
                            # 새로운 타입 시스템: queue, run, error, done
                            data_type = data.get("type")
                            thread_id = data.get("thread_id")
                            stream_id_received = data.get("stream_id")
                            logger.debug(f"data_type: {data_type}, thread_id: {thread_id}")
                            
                            if data_type == "queue":
                                raw_content = data.get("content", "")
                                logger.debug(f"raw_content: {raw_content}")
                                parsed_content = None
                                try:
                                    # content가 JSON 문자열(한글 포함)일 경우 파싱
                                    parsed_content = json.loads(raw_content)
                                    logger.debug(f"parsed_content: {parsed_content}")
                                except Exception as e:
                                    # JSON이 아니면 원문 문자열 유지
                                    parsed_content = raw_content
                                    logger.debug(f"JSON parse failed: {e}, using raw content")

                                payload = {
                                    "type": "queue", 
                                    "content": parsed_content,
                                    "thread_id": thread_id,
                                    "stream_id": stream_id_received
                                }
                                logger.debug(f"Final payload: {payload}")
                                aggregated.append(payload)
                                
                                try:
                                    json_payload = json.dumps(jsonable_encoder(payload), ensure_ascii=False)
                                    yield f"data: {json_payload}\n\n"
                                except Exception as e:
                                    logger.error(f"Failed to serialize payload: {e}", exc_info=True)
                                    yield f"data: {json.dumps({'type': 'error', 'message': f'Serialization error: {str(e)}'}, ensure_ascii=False)}\n\n"
                                
                            elif data_type == "run":
                                raw_content = data.get("content", "")
                                logger.debug(f"Processing RUN message: {raw_content}")
                                try:
                                    parsed_content = json.loads(raw_content)
                                    logger.debug(f"Parsed RUN content: {parsed_content}")
                                except Exception as e:
                                    parsed_content = raw_content
                                    logger.debug(f"RUN JSON parse failed: {e}, using raw content")
                                    
                                payload = {
                                    "type": "run", 
                                    "content": parsed_content,
                                    "thread_id": thread_id,
                                    "stream_id": stream_id_received
                                }
                                logger.debug(f"Sending RUN payload: {payload}")
                                yield f"data: {json.dumps(jsonable_encoder(payload), ensure_ascii=False)}\n\n"
                                
                            elif data_type == "done":
                                raw_content = data.get("content", "")
                                try:
                                    parsed_content = json.loads(raw_content)
                                except Exception:
                                    parsed_content = raw_content
                                    
                                payload = {
                                    "type": "done", 
                                    "content": parsed_content,
                                    "thread_id": thread_id,
                                    "stream_id": stream_id_received
                                }
                                yield f"data: {json.dumps(jsonable_encoder(payload), ensure_ascii=False)}\n\n"
                                break
                                
                            elif data_type == "error":
                                raw_content = data.get("content", "")
                                try:
                                    parsed_content = json.loads(raw_content)
                                except Exception:
                                    parsed_content = raw_content
                                    
                                payload = {
                                    "type": "error", 
                                    "content": parsed_content,
                                    "thread_id": thread_id,
                                    "stream_id": stream_id_received,
                                    "message": data.get('message', 'Unknown error')
                                }
                                yield f"data: {json.dumps(jsonable_encoder(payload), ensure_ascii=False)}\n\n"
                                break
                        
                        await asyncio.sleep(0.1)
                        
                        # consume 작업이 완료되었는지 확인
                        if consume_task.done():
                            if not result_data:  # 더 이상 처리할 데이터가 없으면
                                yield f"data: {json.dumps(jsonable_encoder({'type': 'done', 'content': {'step': 'complete', 'text': 'Stream completed'}, 'thread_id': request.thread_id, 'stream_id': stream_id}), ensure_ascii=False)}\n\n"
                                break
                        
                    except Exception as e:
                        yield f"data: {json.dumps(jsonable_encoder({'type': 'error', 'message': f'Processing error: {str(e)}'}), ensure_ascii=False)}\n\n"
                        break
                        
            except Exception as e:
                yield f"data: {json.dumps(jsonable_encoder({'type': 'error', 'message': f'Stream error: {str(e)}'}), ensure_ascii=False)}\n\n"
            finally:
                try:
                    await consumer.close()
                except:
                    pass
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/event-stream; charset=utf-8",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Access-Control-Allow-Origin": "*"
            }
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"AI assist stream failed: {str(e)}"
        )