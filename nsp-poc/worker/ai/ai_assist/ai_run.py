import asyncio
import os
import json
import signal
import sys
import logging
from datetime import datetime
from typing import Any, Optional, Dict
import traceback

from fastapi.encoders import jsonable_encoder

# [Refactor] Step 3: 통합 로깅 시스템 도입
from shared.logging_config import configure_logging
# 로거 설정
configure_logging(service_name="worker")
logger = logging.getLogger(__name__)

# [Refactor] Step 2: 설정 중앙화
from api.config.settings import settings
from shared.utils import generate_id
from shared.rabbitmq_lib.connection import get_channel
from shared.mongodb_lib.message_manager import MessageManager
from shared.mongodb_lib.memory_manager import MemoryManager
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
        self.settings = settings
        
        try:
            self.message_manager = MessageManager(self.settings.mongodb_url)
            self.memory_manager = MemoryManager(self.settings.mongodb_url)
            logger.info(f"[{self.worker_name}] ✅ MongoDB connection initialized successfully. URI: {self.settings.mongodb_url}")
        except Exception as e:
            logger.error(f"[{self.worker_name}] ❌ Failed to initialize MongoDB: {e}", exc_info=True)
            raise
    
    async def initialize(self):
        """Initialize RabbitMQ connections and publishers"""
        logger.info(f"Initializing {self.worker_name}...")
        
        self.channel = await get_channel()
        
        from shared.rabbitmq_lib.topology import declare_worker_topology
        await declare_worker_topology(self.channel)
        logger.info(f"{self.worker_name} topology declared")
        
        self.consumer = TaskConsumer()
        self.task_publisher = TaskPublisher()
        self.llm_publisher = LLMPublisher()

        try:
            await self.bootstrap_qdrant_if_empty()
        except Exception as e:
            logger.warning(f"[{self.worker_name}] Qdrant bootstrap skipped/failed: {e}")
            logger.debug(f"[{self.worker_name}] Bootstrap error traceback: {traceback.format_exc()}")
        
        try:
            loop = asyncio.get_running_loop()
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, lambda s=sig: self.signal_handler(s, None))
        except (NotImplementedError, RuntimeError):
            signal.signal(signal.SIGINT, self.signal_handler)
            signal.signal(signal.SIGTERM, self.signal_handler)
        
        logger.info(f"{self.worker_name} initialized successfully")

    async def bootstrap_qdrant_if_empty(self):
        """If target Qdrant collection is missing or empty, ingest CSV on startup."""
        worker_id = os.getenv("PM2_INSTANCE_ID", "0")
        if worker_id != "0":
            logger.info(f"[{self.worker_name}] Worker {worker_id}: Skipping bootstrap (only worker 0 performs this task)")
            return
            
        qdrant_url = f"http://{self.settings.qdrant_host}:{self.settings.qdrant_port}"
        collection = self.settings.qdrant_collection
        csv_path = os.getenv("QDRANT_BOOTSTRAP_CSV", "metadata_course.csv")
        org_code = os.getenv("QDRANT_ORG_CODE")

        if not qdrant_url or not collection:
            raise RuntimeError("QDRANT_HOST/QDRANT_COLLECTION not set in settings")
        if not os.path.exists(csv_path):
            raise FileNotFoundError(f"Bootstrap CSV not found: {csv_path}")

        client = QdrantClient(url=qdrant_url)
        try:
            collections_response = client.get_collections()
            cols = [c.name for c in collections_response.collections]
        except Exception as e:
            logger.error(f"Failed to connect to Qdrant at {qdrant_url}: {e}")
            return

        should_ingest = False
        if collection not in cols:
            should_ingest = True
        else:
            try:
                points, _ = client.scroll(collection_name=collection, limit=1)
                if not points:
                    should_ingest = True
            except Exception:
                should_ingest = True

        if should_ingest:
            logger.info(f"[{self.worker_name}] Qdrant collection '{collection}' empty/missing. Ingesting from {csv_path}...")
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, lambda: ingest_courses_csv(csv_path, collection, org_code))
            logger.info(f"[{self.worker_name}] Qdrant bootstrap ingest completed for collection '{collection}'")
        else:
            logger.info(f"[{self.worker_name}] Qdrant collection '{collection}' already populated; skipping ingest")
        
        await self.test_vector_search(qdrant_url, collection, org_code)
    
    async def test_vector_search(self, qdrant_url: str, collection: str, org_code: str):
        """Test vector search functionality after bootstrap"""
        try:
            from shared.qdrant_lib.search_service import retrieve
            test_query = "데이터 분석 머신러닝"
            logger.info(f"[{self.worker_name}] Testing vector search with query: '{test_query}'")
            
            loop = asyncio.get_running_loop()
            search_results = await loop.run_in_executor(None, lambda: retrieve(test_query, collection, limit=3))
            
            if search_results:
                logger.info(f"[{self.worker_name}] ✅ Vector search test successful! Found {len(search_results)} results:")
                for i, result in enumerate(search_results[:2]):
                    payload = result.get('payload', {})
                    course_name = payload.get('metadata', {}).get('course_name', 'No title')
                    logger.info(f"[{self.worker_name}]   {i+1}. {course_name} (score: {result.get('score', 0):.3f})")
            else:
                logger.warning(f"[{self.worker_name}] ⚠️  Vector search test returned no results")
        except Exception as e:
            logger.error(f"[{self.worker_name}] ❌ Vector search test failed: {e}", exc_info=True)
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, shutting down {self.worker_name}...")
        self.running = False
    
    async def send_stream_chunk(self, stream_id: str, chunk: str, chunk_type: str = "chunk", metadata: Dict[str, Any] = None, thread_id: str = None):
        """Send streaming chunk to RabbitMQ"""
        message = {
            "stream_id": stream_id, "thread_id": thread_id, "type": chunk_type,
            "content": chunk, "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(), "worker": self.worker_name
        }
        logger.debug(f"Sending to RabbitMQ: {message}")
        await self.task_publisher.publish_result(f"assist.response.{stream_id}", message)
    
    async def process_message(self, payload: Dict[str, Any]):
        """Process incoming message from queue"""
        message_id = payload.get('message_id', 'N/A')
        stream_id = payload.get("stream_id")
        try:
            logger.info(f"[{self.worker_name}] Processing message: {message_id}")
            
            required_fields = ["stream_id", "message_id", "user_id", "thread_id", "text"]
            for field in required_fields:
                if field not in payload:
                    raise ValueError(f"Missing required field: {field}")
            
            await self.process_ai_assist_message(payload)
            logger.info(f"[{self.worker_name}] Completed message: {message_id}")
            
        except ValueError as e:
            logger.warning(f"[{self.worker_name}] Validation error for message {message_id}: {e}")
            if stream_id:
                await self.send_stream_chunk(stream_id, "", "error", {"message": str(e)})
        except Exception as e:
            logger.error(f"[{self.worker_name}] Processing error for message {message_id}: {e}", exc_info=True)
            if stream_id:
                await self.send_stream_chunk(stream_id, "", "error", {"message": str(e)})
    
    async def process_ai_assist_message(self, message_data: Dict[str, Any]):
        """Process AI assist message with streaming response"""
        stream_id = message_data.get("stream_id")
        thread_id = message_data.get("thread_id")
        try:
            await self.save_user_message(message_data)
            await self.process_with_ai(message_data)
        except Exception as e:
            logger.error(f"[{self.worker_name}] Error processing AI assist for stream {stream_id}: {e}", exc_info=True)
            await self.send_stream_chunk(
                stream_id, json.dumps({"step": "error", "text": "Processing failed"}, ensure_ascii=False),
                "error", {"error": str(e), "message": "An error occurred while processing your request."}, thread_id
            )
    
    async def process_with_ai(self, message_data: Dict[str, Any]):
        """Run LangGraph astream with direct queue streaming"""
        stream_id = message_data.get("stream_id")
        thread_id = message_data.get("thread_id")
        text = message_data.get("text")
        model = message_data.get("model", "default")
        og_code = message_data.get("organization_code")

        try:
            from worker.ai.ai_assist.ai_assist import ai_graph
        except ImportError:
            logger.error(f"[{self.worker_name}] Could not import ai_graph.")
            return
        
        async def send_chunk(chunk: str, metadata: Dict[str, Any] = None):
            await self.send_stream_chunk(stream_id, chunk, "run", metadata or {}, thread_id)
        
        memory_messages = await self.load_memory(og_code, thread_id)
        
        state = {
            "query": text, "memory": memory_messages, "vectorstore": [], "file_search": [],
            "metadata": {
                "user_id": message_data.get("user_id"), "thread_id": thread_id,
                "message_id": message_data.get("message_id"), "org_id": og_code
            },
            "model": model, "stream_sender": send_chunk
        }
        
        try:
            logger.info(f"[{self.worker_name}] Starting LangGraph execution for stream: {stream_id}")
            final_state = None
            async for event in ai_graph.astream(state, stream_mode="values"):
                final_state = event
            final_result = final_state.get("result") if final_state else None
            await self.save_ai_result(message_data, final_result, model)
            await self.send_stream_chunk(
                stream_id, json.dumps({"step": "complete", "text": "AI processing completed"}, ensure_ascii=False),
                "done", {"message": "AI processing completed", "model": model}, thread_id
            )
        except Exception as e:
            logger.error(f"[{self.worker_name}] LangGraph error for stream {stream_id}: {e}", exc_info=True)
            await self.send_stream_chunk(
                stream_id, json.dumps({"step": "error", "text": "LangGraph execution failed"}, ensure_ascii=False),
                "error", {"message": f"LangGraph execution failed: {str(e)}"}, thread_id
            )
    
    async def save_user_message(self, message_data: Dict[str, Any]):
        """사용자 메시지를 MongoDB에 저장"""
        og_code = message_data.get("organization_code")
        thread_id = message_data.get("thread_id")
        user_id = message_data.get("user_id")
        try:
            logger.info(f"[{self.worker_name}] Attempting to save user message - OG: {og_code}, Thread: {thread_id}, User: {user_id}")
            from shared.mongodb_lib.thread_manager import ThreadManager
            thread_manager = ThreadManager(self.settings.mongodb_url)
            thread = thread_manager.get_thread(og_code, thread_id)
            if not thread:
                logger.info(f"[{self.worker_name}] Thread {thread_id} not found, creating new thread")
                created_thread_id = thread_manager.add_user_thread(og_code, user_id, "ai_assist")
                if created_thread_id != thread_id:
                    logger.warning(f"[{self.worker_name}] Created thread ID {created_thread_id} differs from expected {thread_id}")
                message_data['thread_id'] = created_thread_id
            
            user_content = {
                "text": message_data.get("text"), "timestamp": datetime.now().isoformat(),
                "user_id": user_id, "stream_id": message_data.get("stream_id")
            }
            success = self.message_manager.add_user_message(og_code, message_data['thread_id'], message_data.get("message_id"), user_content)
            if success:
                logger.info(f"[{self.worker_name}] ✅ User message saved to MongoDB - Thread: {message_data['thread_id']}")
            else:
                logger.warning(f"[{self.worker_name}] ❌ Failed to save user message to MongoDB - Thread: {message_data['thread_id']}")
        except Exception as e:
            logger.error(f"[{self.worker_name}] ❌ Error saving user message to MongoDB: {e}", exc_info=True)

    async def save_ai_result(self, message_data: Dict[str, Any], final_result: Any, model: str):
        """AI 실행 결과를 MongoDB에 저장"""
        og_code = message_data.get("organization_code")
        thread_id = message_data.get("thread_id")
        try:
            logger.info(f"[{self.worker_name}] Attempting to save AI result - OG: {og_code}, Thread: {thread_id}")
            ai_message_id = f"{message_data.get('message_id')}_ai"
            final_result_jsonable = json.loads(json.dumps(jsonable_encoder(final_result)))
            ai_content = {
                "text": str(final_result_jsonable), "model": model,
                "result_type": type(final_result).__name__, "timestamp": datetime.now().isoformat()
            }
            if isinstance(final_result_jsonable, (list, dict)):
                ai_content["structured_result"] = final_result_jsonable
            success = self.message_manager.add_ai_message(og_code, thread_id, ai_message_id, ai_content)
            if success:
                logger.info(f"[{self.worker_name}] ✅ AI result saved to MongoDB - Thread: {thread_id}")
            else:
                logger.warning(f"[{self.worker_name}] ❌ Failed to save AI result to MongoDB - Thread: {thread_id}")
        except Exception as e:
            logger.error(f"[{self.worker_name}] ❌ Error saving AI result to MongoDB: {e}", exc_info=True)
    
    async def load_memory(self, og_code: str, thread_id: str):
        """MongoDB에서 메모리 로드 - Pydantic AI 메시지 형식으로"""
        try:
            from pydantic_ai.messages import ModelRequest, ModelResponse, SystemPromptPart, UserPromptPart, TextPart
            memory_history = self.memory_manager.get_memory(og_code, thread_id)
            pydantic_messages = []
            for msg in memory_history:
                role, text = msg.get("role", "user"), msg.get("text", "")
                if role == "long_term_memory":
                    pydantic_messages.append(ModelRequest(parts=[SystemPromptPart(f"[Previous Context] {text}")]))
                elif role in ["user", "human"]:
                    pydantic_messages.append(ModelRequest(parts=[UserPromptPart(text)]))
                elif role in ["ai", "assistant"]:
                    pydantic_messages.append(ModelResponse(parts=[TextPart(text)]))
            logger.info(f"[{self.worker_name}] Loaded {len(pydantic_messages)} Pydantic AI messages from memory")
            return pydantic_messages
        except Exception as e:
            logger.error(f"[{self.worker_name}] Error loading memory: {e}", exc_info=True)
            return []
    
    async def start_consuming(self):
        """Start consuming messages from the AI assist queue"""
        logger.info(f"[{self.worker_name}] Starting to consume messages from queue: {self.settings.rabbitmq_assist_queue}")
        try:
            await self.consumer.consume_tasks(
                queue_name=self.settings.rabbitmq_assist_queue,
                callback=self.process_message
            )
            while self.running:
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"[{self.worker_name}] Consumption error: {e}", exc_info=True)
            raise
        finally:
            await self.cleanup()
    
    async def cleanup(self):
        """Clean up resources"""
        logger.info(f"[{self.worker_name}] Cleaning up resources...")
        try:
            if self.consumer: await self.consumer.close()
            if self.task_publisher: await self.task_publisher.close()
            if self.llm_publisher: await self.llm_publisher.close()
            if self.channel and not self.channel.is_closed: await self.channel.close()
        except Exception as e:
            logger.warning(f"[{self.worker_name}] Cleanup error: {e}", exc_info=True)
        logger.info(f"[{self.worker_name}] Cleanup completed")
    
    async def run(self):
        """Main worker run method"""
        try:
            await self.initialize()
            await self.start_consuming()
        except Exception as e:
            logger.critical(f"[{self.worker_name}] Worker error: {e}", exc_info=True)
            sys.exit(1)

async def main():
    """Main entry point for AI assist worker"""
    logger.info("Starting AI Assist Worker...")
    worker = AIAssistWorker()
    await worker.run()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("AI Assist worker stopped by user")
    except Exception as e:
        logger.critical(f"AI Assist worker failed: {e}", exc_info=True)
        sys.exit(1)