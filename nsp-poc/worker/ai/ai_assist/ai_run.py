import asyncio
import os
import json
import signal
import sys
import uuid
from datetime import datetime
from typing import Any, Optional, Dict
import traceback
from shared.utils import generate_id  # 공용화된 ID 생성 사용
from fastapi.encoders import jsonable_encoder
from shared.rabbitmq_lib.config import get_rabbitmq_config
import time
import random

from shared.rabbitmq_lib.connection import get_channel
from shared.mongodb_lib.message_manager import MessageManager
from shared.mongodb_lib.config import MongoConfig
from shared.rabbitmq_lib.consumer import TaskConsumer
from shared.rabbitmq_lib.publisher import TaskPublisher, LLMPublisher
from qdrant_client import QdrantClient
from shared.qdrant_lib.qdrant_client import ingest_courses_csv



class AIAssistWorker:
    """AI Assist Worker that processes messages from queue and streams responses"""
    
    def __init__(self):
        self.consumer = None
        self.task_publisher = None
        self.llm_publisher = None
        self.channel = None
        self.running = True
        self.worker_name = "ai_assist_worker"
        self.config = get_rabbitmq_config()
        
        # MongoDB 설정 및 매니저 초기화
        try:
            self.mongo_config = MongoConfig()
            self.message_manager = MessageManager(self.mongo_config)
            print(f"[{self.worker_name}] ✅ MongoDB connection initialized successfully")
            print(f"[{self.worker_name}] MongoDB URI: {self.mongo_config.mongo_uri}")
        except Exception as e:
            print(f"[{self.worker_name}] ❌ Failed to initialize MongoDB: {e}")
            raise
    
    async def initialize(self):
        """Initialize RabbitMQ connections and publishers"""
        print(f"Initializing {self.worker_name}...")
        
        # Get channel
        self.channel = await get_channel()
        
        # Declare topology to ensure queues exist
        from shared.rabbitmq_lib.topology import declare_worker_topology
        await declare_worker_topology(self.channel)
        print(f"{self.worker_name} topology declared")
        
        # Create consumer and publishers
        self.consumer = TaskConsumer()
        self.task_publisher = TaskPublisher()
        self.llm_publisher = LLMPublisher()

        # Bootstrap Qdrant collection with CSV embeddings if empty
        try:
            await self.bootstrap_qdrant_if_empty()
        except Exception as e:
            print(f"[{self.worker_name}] Qdrant bootstrap skipped/failed: {e}")
            print(f"[{self.worker_name}] Bootstrap error traceback: {traceback.format_exc()}")
        
        # Setup signal handlers (prefer asyncio loop handlers when available)
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                try:
                    loop.add_signal_handler(sig, lambda s=sig: self.signal_handler(s, None))
                except NotImplementedError:
                    signal.signal(sig, self.signal_handler)
        except RuntimeError:
            # No running loop yet; fall back to standard signal handling
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
        
        print(f"{self.worker_name} initialized successfully")

    async def bootstrap_qdrant_if_empty(self):
        """If target Qdrant collection is missing or empty, ingest CSV on startup."""
        # Only worker instance 0 should perform bootstrap to avoid duplicate work
        worker_id = os.getenv("PM2_INSTANCE_ID", "0")
        if worker_id != "0":
            print(f"[{self.worker_name}] Worker {worker_id}: Skipping bootstrap (only worker 0 performs this task)")
            return
            
        qdrant_url = os.getenv("QDRANT_URL")
        collection = os.getenv("QDRANT_COLLECTION")
        csv_path = os.getenv("QDRANT_BOOTSTRAP_CSV", "metadata_course.csv")
        org_code = os.getenv("QDRANT_ORG_CODE")

        if not qdrant_url:
            raise RuntimeError("QDRANT_URL is not set")
        if not collection:
            raise RuntimeError("QDRANT_COLLECTION is not set")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Bootstrap CSV not found: {csv_path}")

        client = QdrantClient(url=qdrant_url)
        cols = [c.name for c in client.get_collections().collections]

        should_ingest = False
        if collection not in cols:
            should_ingest = True
        else:
            # Check if collection has at least one point
            try:
                points, _ = client.scroll(collection_name=collection, limit=1)
                if not points:
                    should_ingest = True
            except Exception:
                should_ingest = True

        if should_ingest:
            print(f"[{self.worker_name}] Qdrant collection '{collection}' empty/missing. Ingesting from {csv_path}...")
            # Run blocking ingest in a worker thread to avoid blocking event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: ingest_courses_csv(csv_path, collection, org_code))
            print(f"[{self.worker_name}] Qdrant bootstrap ingest completed for collection '{collection}'")
        else:
            print(f"[{self.worker_name}] Qdrant collection '{collection}' already populated; skipping ingest")
        
        # Perform vector search test after ensuring data exists
        await self.test_vector_search(qdrant_url, collection, org_code)
    
    async def test_vector_search(self, qdrant_url: str, collection: str, org_code: str):
        """Test vector search functionality after bootstrap"""
        try:
            from shared.qdrant_lib.search_service import retrieve
            
            # Test query
            test_query = "데이터 분석 머신러닝"
            print(f"[{self.worker_name}] Testing vector search with query: '{test_query}'")
            
            # Perform vector search
            loop = asyncio.get_running_loop()
            search_results = await loop.run_in_executor(
                None, 
                lambda: retrieve(test_query, collection, limit=3)
            )
            
            if search_results:
                print(f"[{self.worker_name}] ✅ Vector search test successful! Found {len(search_results)} results:")
                for i, result in enumerate(search_results[:2]):  # Show first 2 results
                    score = result.get('score', 0)
                    payload = result.get('payload', {})
                    metadata = payload.get('metadata', {})
                    course_name = metadata.get('course_name', 'No title')
                    print(f"[{self.worker_name}]   {i+1}. {course_name} (score: {score:.3f})")
            else:
                print(f"[{self.worker_name}] ⚠️  Vector search test returned no results")
                
        except Exception as e:
            print(f"[{self.worker_name}] ❌ Vector search test failed: {e}")
            import traceback
            print(f"[{self.worker_name}] Traceback: {traceback.format_exc()}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        print(f"Received signal {signum}, shutting down {self.worker_name}...")
        self.running = False
    
    def generate_id(self) -> str:
        """Generate unique message ID"""
        return generate_id()
    
    async def send_stream_chunk(
        self, 
        stream_id: str, 
        chunk: str, 
        chunk_type: str = "chunk",
        metadata: Dict[str, Any] = None,
        thread_id: str = None
    ):
        """Send streaming chunk to RabbitMQ"""
        message = {
            "stream_id": stream_id,
            "thread_id": thread_id,
            "type": chunk_type,
            "content": chunk,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
            "worker": self.worker_name
        }
        print(f"[DEBUG] Sending to RabbitMQ: {message}")
        await self.task_publisher.publish_result(
            f"assist.response.{stream_id}",
            message
        )
    
    async def process_message(self, payload: Dict[str, Any]):
        """Process incoming message from queue"""
        try:
            print(f"[{self.worker_name}] Processing message: {payload.get('message_id')}")
            
            # Validate required fields
            required_fields = ["stream_id", "message_id", "user_id", "thread_id", "text"]
            for field in required_fields:
                if field not in payload:
                    raise ValueError(f"Missing required field: {field}")
            
            # 큐에서 메시지 받았을 때는 바로 AI 처리 시작 (queue 메시지는 API에서 처리)
            stream_id = payload.get("stream_id")
            thread_id = payload.get("thread_id")
            print(f"[{self.worker_name}] Processing message for stream: {stream_id}")
            
            # Process with AI
            await self.process_ai_assist_message(payload)
            
            print(f"[{self.worker_name}] Completed message: {payload['message_id']}")
            
        except ValueError as e:
            print(f"[{self.worker_name}] Validation error: {e}")
            stream_id = payload.get("stream_id")
            if stream_id:
                await self.send_stream_chunk(stream_id, "", "error", {"message": str(e)})
            
        except Exception as e:
            print(f"[{self.worker_name}] Processing error: {e}")
            stream_id = payload.get("stream_id")
            if stream_id:
                await self.send_stream_chunk(stream_id, "", "error", {"message": str(e)})
    
    async def process_ai_assist_message(self, message_data: Dict[str, Any]):
        """Process AI assist message with streaming response"""
        
        stream_id = message_data.get("stream_id")
        user_id = message_data.get("user_id")
        thread_id = message_data.get("thread_id")
        message_id = message_data.get("message_id")
        text = message_data.get("text")
        model = message_data.get("model", "default")
        
        try:
            # 사용자 메시지를 MongoDB에 저장
            await self.save_user_message(message_data)
            
            # Process with real AI (run 메시지는 이미 process_message에서 전송됨)
            await self.process_with_ai(stream_id, text, model, message_data)
            
        except Exception as e:
            print(f"[{self.worker_name}] Error processing AI assist: {e}")
            await self.send_stream_chunk(
                stream_id,
                json.dumps({"step": "error", "text": "Processing failed"}, ensure_ascii=False),
                "error",
                {
                    "error": str(e), 
                    "message": "An error occurred while processing your request."
                },
                thread_id
            )
    
    async def process_with_ai(self, stream_id: str, text: str, model: str, message_data: Dict[str, Any]):
        """Run LangGraph astream with direct queue streaming"""
        
        # ai_assist 모듈에서 그래프 가져오기
        try:
            from worker.ai.ai_assist.ai_assist import ai_graph
        except ImportError:
            print(f"[{self.worker_name}] Could not import ai_graph, falling back to simulator")
            return
        
        # 큐 전송 함수 정의
        thread_id = message_data.get("thread_id")
        async def send_chunk(chunk: str, metadata: Dict[str, Any] = None):
            await self.send_stream_chunk(stream_id, chunk, "run", metadata or {}, thread_id)
        
        # 메모리 로드
        og_code = message_data.get("organization_code")
        thread_id = message_data.get("thread_id")
        memory_messages = await self.load_memory(og_code, thread_id)
        
        # 상태 구성
        state = {
            "query": text,
            "memory": memory_messages,  # MongoDB에서 로드한 메모리
            "vectorstore": [],
            "file_search": [],
            "metadata": {
                "user_id": message_data.get("user_id"),
                "thread_id": message_data.get("thread_id"),
                "message_id": message_data.get("message_id"),
                "org_id": og_code
            },
            "model": model,
            # 큐 전송 함수 주입
            "stream_sender": send_chunk
        }
        
        # 그래프 실행
        try:
            print(f"[{self.worker_name}] Starting LangGraph execution for stream: {stream_id}")
            
            final_state = None
            async for event in ai_graph.astream(state, stream_mode="values"):
                final_state = event

            final_result = final_state.get("result") if final_state else None
                    
            # MongoDB에 결과 저장
            await self.save_ai_result(message_data, final_result, model)
                    
            await self.send_stream_chunk(
                stream_id, 
                json.dumps({"step": "complete", "text": "AI processing completed"}, ensure_ascii=False), 
                "done", 
                {
                    "message": "AI processing completed",
                    "model": model
                },
                thread_id
            )
            
        except Exception as e:
            print(f"[{self.worker_name}] LangGraph error: {e}")
            await self.send_stream_chunk(
                stream_id, 
                json.dumps({"step": "error", "text": "LangGraph execution failed"}, ensure_ascii=False), 
                "error", 
                {
                    "message": f"LangGraph execution failed: {str(e)}"
                },
                thread_id
            )
    
    async def save_user_message(self, message_data: Dict[str, Any]):
        """사용자 메시지를 MongoDB에 저장"""
        try:
            og_code = message_data.get("organization_code")
            thread_id = message_data.get("thread_id")
            message_id = message_data.get("message_id")
            text = message_data.get("text")
            user_id = message_data.get("user_id")
            
            print(f"[{self.worker_name}] Attempting to save user message - OG: {og_code}, Thread: {thread_id}, User: {user_id}")
            
            # 스레드 존재 확인 및 생성
            from shared.mongodb_lib.thread_manager import ThreadManager
            thread_manager = ThreadManager(self.mongo_config)
            
            # 스레드 존재 여부 확인
            thread = thread_manager.get_thread(og_code, thread_id)
            if not thread:
                print(f"[{self.worker_name}] Thread {thread_id} not found, creating new thread")
                # 새 스레드 생성
                created_thread_id = thread_manager.add_user_thread(og_code, user_id, "ai_assist")
                if created_thread_id != thread_id:
                    print(f"[{self.worker_name}] Warning: Created thread ID {created_thread_id} differs from expected {thread_id}")
                thread_id = created_thread_id
                message_data['thread_id'] = created_thread_id
            
            # 사용자 메시지 콘텐츠 구성
            user_content = {
                "text": text,
                "timestamp": datetime.now().isoformat(),
                "user_id": user_id,
                "stream_id": message_data.get("stream_id")
            }
            
            # MongoDB에 사용자 메시지 저장
            success = self.message_manager.add_user_message(
                og_code,
                thread_id,
                message_id,
                user_content
            )
            
            if success:
                print(f"[{self.worker_name}] ✅ User message saved to MongoDB - Thread: {thread_id}")
            else:
                print(f"[{self.worker_name}] ❌ Failed to save user message to MongoDB - Thread: {thread_id}")
                
        except Exception as e:
            print(f"[{self.worker_name}] ❌ Error saving user message to MongoDB: {e}")
            import traceback
            print(f"[{self.worker_name}] Traceback: {traceback.format_exc()}")

    async def save_ai_result(self, message_data: Dict[str, Any], final_result: Any, model: str):
        """AI 실행 결과를 MongoDB에 저장"""
        try:
            og_code = message_data.get("organization_code")  # 조직 코드
            thread_id = message_data.get("thread_id")
            message_id = message_data.get("message_id")
            
            print(f"[{self.worker_name}] Attempting to save AI result - OG: {og_code}, Thread: {thread_id}")
            
            # AI 응답 메시지 ID 생성 (사용자 메시지 ID와 구분)
            ai_message_id = f"{message_id}_ai"
            
            # Pydantic 모델을 JSON으로 변환
            final_result_jsonable = json.loads(json.dumps(jsonable_encoder(final_result)))

            # AI 응답 콘텐츠 구성
            ai_content = {
                "text": str(final_result_jsonable),
                "model": model,
                "result_type": type(final_result).__name__,
                "timestamp": datetime.now().isoformat()
            }
            
            # 구조화된 결과가 있는 경우 추가 정보 저장
            if isinstance(final_result_jsonable, (list, dict)):
                ai_content["structured_result"] = final_result_jsonable
            
            # MongoDB에 AI 메시지 저장
            success = self.message_manager.add_ai_message(
                og_code, 
                thread_id, 
                ai_message_id,  # AI 메시지용 별도 ID 사용
                ai_content
            )
            
            if success:
                print(f"[{self.worker_name}] ✅ AI result saved to MongoDB - Thread: {thread_id}")
            else:
                print(f"[{self.worker_name}] ❌ Failed to save AI result to MongoDB - Thread: {thread_id}")
                
        except Exception as e:
            print(f"[{self.worker_name}] ❌ Error saving AI result to MongoDB: {e}")
            import traceback
            print(f"[{self.worker_name}] Traceback: {traceback.format_exc()}")
    
    async def load_memory(self, og_code: str, thread_id: str):
        """MongoDB에서 메모리 로드 - Pydantic AI 메시지 형식으로"""
        try:
            from shared.mongodb_lib.memory_manager import MemoryManager
            from pydantic_ai.messages import (
                ModelRequest, ModelResponse, 
                SystemPromptPart, UserPromptPart, TextPart
            )
            
            memory_manager = MemoryManager(self.mongo_config)
            
            # 메모리 히스토리 가져오기
            memory_history = memory_manager.get_memory(og_code, thread_id)
            
            # Pydantic AI 메시지 객체로 변환
            pydantic_messages = []
            for msg in memory_history:
                role = msg.get("role", "user")
                text = msg.get("text", "")
                
                if role == "long_term_memory":
                    # 장기 메모리는 시스템 프롬프트로 처리
                    system_request = ModelRequest(parts=[
                        SystemPromptPart(f"[Previous Context] {text}")
                    ])
                    pydantic_messages.append(system_request)
                    
                elif role in ["user", "human"]:
                    # 사용자 메시지
                    user_request = ModelRequest(parts=[
                        UserPromptPart(text)
                    ])
                    pydantic_messages.append(user_request)
                    
                elif role in ["ai", "assistant"]:
                    # AI 응답
                    ai_response = ModelResponse(parts=[
                        TextPart(text)
                    ])
                    pydantic_messages.append(ai_response)
            
            print(f"[{self.worker_name}] Loaded {len(pydantic_messages)} Pydantic AI messages from memory")
            return pydantic_messages
            
        except Exception as e:
            print(f"[{self.worker_name}] Error loading memory: {e}")
            return []
    
    async def simulate_ai_processing(self, stream_id: str, text: str, model: str):
        """Simulate AI processing with streaming chunks (LangGraph-like node steps and random scenario)"""
        try:
            # Send processing status (LangGraph node: supervisor)
            await self.send_stream_chunk(
                stream_id,
                json.dumps({"step": "supervisor", "text": f"[supervisor] 분류를 시작합니다… (model={model})"}, ensure_ascii=False),
                "processing",
                {"model": model}
            )

            # Simulate processing delay
            await asyncio.sleep(1)

            # Generate structured test response parts (simulate LangGraph-like traces)
            candidate_scenarios = [
                # A) 일반 대화 → chat
                [
                    {"step": "supervisor", "text": "[supervisor] 라우팅 결과: chat (confidence=0.78, reason=일반 질의)"},
                    {"step": "chat", "text": "(스트리밍) 안녕하세용"},
                    {"step": "chat", "text": "(스트리밍) 너의 이름은 테스트야"},
                    {"step": "chat", "text": "(스트리밍) 사용자 질문에 대한 답변 본문..."},
                ],
                # B) 삼성 관련 → rubicon
                [
                    {"step": "supervisor", "text": "[supervisor] 라우팅 결과: rubicon (confidence=0.92, reason=삼성 키워드)"},
                    {"step": "rubicon", "text": "[rubicon] 삼성 관련 질의 처리 시작…"},
                    {"step": "rubicon", "text": "(스트리밍) 갤럭시 라인업은 S/Z/A로 구분됩니다."},
                    {"step": "rubicon", "text": "(스트리밍) S24 Ultra와 Z Fold6 비교 요약…"},
                ],
                # C) 코스 추천 → course_recommand (단일 JSON 결과를 한 번에 보내는 케이스 흉내)
                [
                    {"step": "supervisor", "text": "[supervisor] 라우팅 결과: course_recommand (confidence=0.84, reason=추천+학습)"},
                    {"step": "course_recommand", "json": json.dumps({
                        "step": "course_recommand",
                        "result": {
                            "goal": "데이터 엔지니어 전환",
                            "level": "intermediate",
                            "total_estimated_hours": 60,
                            "prerequisites": ["Python 기본", "Git", "SQL 기초"],
                            "tracks": [
                                {
                                    "name": "Fundamentals-First",
                                    "steps": [
                                        {"title": "데이터 모델링 기초", "objective": "정규화/ERD/키 설계", "estimated_hours": 6, "resources": []},
                                        {"title": "SQL 심화", "objective": "윈도우/CTE/튜닝", "estimated_hours": 8, "resources": []},
                                        {"title": "ETL 파이프라인", "objective": "배치/스케줄링/모니터링", "estimated_hours": 10, "resources": []}
                                    ]
                                }
                            ],
                            "notes": "주 6~8시간 기준 8주 예상"
                        }
                    }, ensure_ascii=False)},
                ],
            ]
            response_parts = random.choice(candidate_scenarios)

            # Stream response parts with delays
            for i, part in enumerate(response_parts):
                await self.send_stream_chunk(
                    stream_id,
                    json.dumps(part, ensure_ascii=False),
                    "queue",
                    {
                        "chunk_index": i,
                        "total_chunks": len(response_parts),
                        "model": model
                    }
                )
                # Add realistic delay between chunks
                await asyncio.sleep(random.uniform(0.2, 0.8))

            # Send completion signal (now JSON content for consistency, updated message)
            await self.send_stream_chunk(
                stream_id,
                json.dumps({"step": "complete", "text": "AI Assist processing completed (simulated)"}, ensure_ascii=False),
                "done",
                {
                    "total_chunks": len(response_parts),
                    "model": model,
                    "processing_time": f"{len(response_parts) * 0.5:.1f}s"
                }
            )

            print(f"[{self.worker_name}] Completed streaming for: {stream_id}")

        except Exception as e:
            print(f"[{self.worker_name}] Stream error: {e}")
            await self.send_stream_chunk(
                stream_id,
                json.dumps({"step": "error", "text": "Streaming failed"}, ensure_ascii=False),
                "error",
                {"error": str(e)}
            )
    
    async def start_consuming(self):
        """Start consuming messages from the AI assist queue"""
        print(f"[{self.worker_name}] Starting to consume messages...")
        
        try:
            # Define callback wrapper
            async def message_callback(payload: dict):
                await self.process_message(payload)
            
            # Start consuming from queue (not routing key)
            await self.consumer.consume_tasks(
                queue_name=self.config.assist_queue,
                callback=message_callback
            )
            
            # Keep running until signal received
            while self.running:
                await asyncio.sleep(1)
                
        except Exception as e:
            print(f"[{self.worker_name}] Consumption error: {e}")
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        print(f"[{self.worker_name}] Cleaning up resources...")
        
        try:
            if self.consumer:
                await self.consumer.close()
            
            if self.task_publisher:
                await self.task_publisher.close()
                
            if self.llm_publisher:
                await self.llm_publisher.close()
                
            if self.channel and not self.channel.is_closed:
                await self.channel.close()
        except Exception as e:
            print(f"[{self.worker_name}] Cleanup error: {e}")
        
        print(f"[{self.worker_name}] Cleanup completed")
    
    async def run(self):
        """Main worker run method"""
        try:
            await self.initialize()
            await self.start_consuming()
        except Exception as e:
            print(f"[{self.worker_name}] Worker error: {e}")
            sys.exit(1)


async def main():
    """Main entry point for AI assist worker"""
    print("Starting AI Assist Worker...")
    
    worker = AIAssistWorker()
    await worker.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("AI Assist worker stopped by user")
    except Exception as e:
        print(f"AI Assist worker failed: {e}")
        sys.exit(1)