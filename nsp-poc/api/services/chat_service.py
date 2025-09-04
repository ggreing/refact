from typing import AsyncGenerator, Optional
import uuid
import json
from datetime import datetime

from api.models.chat import Message, MessageType, MessageStatus
from api.schemas.chat import ChatRequest, ChatResponse
from shared.rabbitmq_lib.publisher import ChatPublisher
from shared.utils import generate_id  # 공용화된 ID 생성 사용



class ChatService:
    """Chat service for handling chat operations"""
    
    def __init__(self):
        self.active_threads = {}
        self.publisher = None
    
    async def initialize(self):
        """Initialize RabbitMQ publisher"""
        if not self.publisher:
            self.publisher = ChatPublisher()
    
    def generate_id(self) -> str:
        """Generate unique message ID"""
        return generate_id()
    
    def create_thread_id(self) -> str:
        """Generate unique thread ID"""
        return str(uuid.uuid4())
    
    async def process_chat_message(
        self, 
        request: ChatRequest
    ) -> tuple[str, str, str]:
        """
        Process chat message and return message_id, thread_id, user_message_id
        """
        await self.initialize()
        
        thread_id = request.thread_id or self.create_thread_id()
        user_message_id = self.generate_id()
        assistant_message_id = self.generate_id()
        
        # Create user message
        user_message = Message(
            id=user_message_id,
            thread_id=thread_id,
            user_id=request.user_id,
            message_type=MessageType.USER,
            content=request.text,
            status=MessageStatus.COMPLETED
        )
        
        # Store message (in production, this would go to database)
        print(f"User message: {user_message.model_dump()}")
        
        # Prepare message for routing queue
        routing_message = {
            "user_id": request.user_id,
            "thread_id": thread_id,
            "message_id": assistant_message_id,
            "text": request.text,
            "function": "chat",  # Specify the AI function
            "memory": [],  # TODO: Load from database
            "vectorstore": [],  # TODO: Load from database
            "metadata": {
                "user_message_id": user_message_id,
                "timestamp": datetime.now().isoformat()
            }
        }
        
        # Send to routing queue
        await self.publisher.publish_message(
            session_id=thread_id,
            user_message=json.dumps(routing_message),
            user_id=request.user_id
        )
        
        print(f"Sent message to routing queue: {assistant_message_id}")
        
        return assistant_message_id, thread_id, user_message_id
    
    async def process_ai_assist_message(
        self,
        request: ChatRequest,
        task_type: str,
        context: dict = None,
        parameters: dict = None
    ) -> tuple[str, str, str]:
        """
        Process AI assist message and return message_id, thread_id, user_message_id
        """
        await self.initialize()
        
        thread_id = request.thread_id or self.create_thread_id()
        user_message_id = self.generate_id()
        assistant_message_id = self.generate_id()
        
        # Create user message
        user_message = Message(
            id=user_message_id,
            thread_id=thread_id,
            user_id=request.user_id,
            message_type=MessageType.USER,
            content=request.text,
            status=MessageStatus.COMPLETED
        )
        
        # Store message (in production, this would go to database)
        print(f"AI Assist user message: {user_message.model_dump()}")
        
        # Prepare message for routing queue with AI assist context
        routing_message = {
            "user_id": request.user_id,
            "thread_id": thread_id,
            "message_id": assistant_message_id,
            "text": request.text,
            "function": "ai_assist",  # Specify the AI assist function
            "task_type": task_type,
            "context": context or {},
            "parameters": parameters or {},
            "memory": [],  # TODO: Load from database
            "vectorstore": [],  # TODO: Load from database
            "metadata": {
                "user_message_id": user_message_id,
                "timestamp": datetime.now().isoformat(),
                "ai_assist_task": task_type
            }
        }
        
        # Send to AI assist routing queue  
        await self.publisher.publish_message(
            session_id=thread_id,
            user_message=json.dumps(routing_message),
            user_id=request.user_id
        )
        
        print(f"Sent AI assist message to routing queue: {assistant_message_id}")
        
        return assistant_message_id, thread_id, user_message_id
    
    async def generate_chat_stream(
        self, 
        message_id: str, 
        thread_id: str, 
        user_text: str
    ) -> AsyncGenerator[str, None]:
        """
        Generate Server-Sent Events stream for chat response
        This now listens to RabbitMQ stream instead of generating fake responses
        """
        # Initial status
        yield f"data: {{'message_id': '{message_id}', 'status': 'sent_to_queue', 'text': 'Message sent to AI processing queue'}}\n\n"
        
        # TODO: Connect to RabbitMQ stream queue to get real-time AI responses
        # For now, simulate the old behavior
        import asyncio
        await asyncio.sleep(1)
        
        # Processing status  
        yield f"data: {{'message_id': '{message_id}', 'status': 'processing', 'text': 'AI is processing your message...'}}\n\n"
        
        await asyncio.sleep(2)
        
        # Final response (this should come from the AI worker stream)
        response_text = f"AI is processing: {user_text}"
        yield f"data: {{'message_id': '{message_id}', 'status': 'completed', 'response': '{response_text}'}}\n\n"
        
        # End of stream
        yield "data: [DONE]\n\n"
    
    async def generate_ai_assist_stream(
        self,
        message_id: str,
        thread_id: str,
        task_type: str,
        content: str,
        context: dict = None
    ) -> AsyncGenerator[str, None]:
        """
        Generate Server-Sent Events stream for AI assist response
        """
        # Initial status
        yield f"data: {{'message_id': '{message_id}', 'status': 'sent_to_queue', 'task_type': '{task_type}', 'text': 'AI assist task sent to processing queue'}}\n\n"
        
        # TODO: Connect to RabbitMQ stream queue to get real-time AI responses
        # For now, simulate AI assist processing
        import asyncio
        await asyncio.sleep(1)
        
        # Task-specific processing status
        task_messages = {
            "code_analysis": "Analyzing code for potential issues and improvements...",
            "documentation": "Generating comprehensive documentation...",
            "debugging": "Identifying and analyzing potential bugs...",
            "optimization": "Analyzing code for performance optimizations...",
            "code_review": "Performing comprehensive code review...",
            "refactoring": "Analyzing code structure for refactoring opportunities..."
        }
        
        processing_message = task_messages.get(task_type, f"Processing {task_type} task...")
        yield f"data: {{'message_id': '{message_id}', 'status': 'processing', 'task_type': '{task_type}', 'text': '{processing_message}'}}\n\n"
        
        await asyncio.sleep(3)
        
        # Task completion with simulated response
        response_text = f"AI Assistant has completed the {task_type} task for your content."
        
        # Add task-specific response details
        if context:
            if context.get('language'):
                response_text += f" Language: {context['language']}."
            if context.get('analysis_type'):
                response_text += f" Analysis type: {context['analysis_type']}."
        
        yield f"data: {{'message_id': '{message_id}', 'status': 'completed', 'task_type': '{task_type}', 'response': '{response_text}'}}\n\n"
        
        # End of stream
        yield "data: [DONE]\n\n"


# Global service instance
chat_service = ChatService()