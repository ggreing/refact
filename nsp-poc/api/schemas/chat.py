from pydantic import BaseModel, Field
from typing import List, Optional
from fastapi import UploadFile


class ChatRequest(BaseModel):
    """Chat request schema"""
    user_id: str = Field(..., description="User ID")
    thread_id: Optional[str] = Field(None, description="Thread ID (optional for new thread)")
    text: str = Field(..., description="Message text")


class ChatResponse(BaseModel):
    """Chat response schema"""
    message_id: str = Field(..., description="Generated message ID")
    thread_id: str = Field(..., description="Thread ID")
    status: str = Field(..., description="Response status")
    response: Optional[str] = Field(None, description="AI response")


class ThreadCreateRequest(BaseModel):
    """Thread creation request schema"""
    user_id: str = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Thread title")


class ThreadResponse(BaseModel):
    """Thread response schema"""
    thread_id: str = Field(..., description="Thread ID")
    user_id: str = Field(..., description="User ID")
    title: Optional[str] = Field(None, description="Thread title")
    created_at: str = Field(..., description="Creation timestamp")


class HealthResponse(BaseModel):
    """Health check response schema"""
    status: str = Field(..., description="Service status")
    services: List[str] = Field(..., description="Available services")
    version: str = Field(..., description="API version")