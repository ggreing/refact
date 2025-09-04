from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from enum import Enum


class MessageType(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class FileInfo(BaseModel):
    """File information model"""
    filename: str
    file_type: str
    file_size: int
    file_url: Optional[str] = None


class Message(BaseModel):
    """Chat message model"""
    id: str = Field(..., description="Unique message ID")
    thread_id: str = Field(..., description="Thread ID")
    user_id: str = Field(..., description="User ID")
    message_type: MessageType = Field(..., description="Message type")
    content: str = Field(..., description="Message content")
    files: List[FileInfo] = Field(default_factory=list, description="Attached files")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    status: MessageStatus = Field(default=MessageStatus.PENDING, description="Message status")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")


class Thread(BaseModel):
    """Chat thread model"""
    id: str = Field(..., description="Unique thread ID")
    user_id: str = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Thread title")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    message_count: int = Field(default=0, description="Number of messages in thread")