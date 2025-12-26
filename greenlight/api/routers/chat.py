"""Chat router for OmniMind integration."""

import asyncio
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


class ChatMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    project_path: Optional[str] = None
    conversation_id: Optional[str] = None


class ChatResponse(BaseModel):
    message: str
    conversation_id: str


# Simple in-memory conversation store
conversations: dict[str, list[ChatMessage]] = {}


@router.post("/", response_model=ChatResponse)
async def send_message(request: ChatRequest):
    """Send a message to OmniMind and get a response."""
    import uuid
    
    # Get or create conversation
    conv_id = request.conversation_id or str(uuid.uuid4())
    if conv_id not in conversations:
        conversations[conv_id] = []
    
    # Add user message
    conversations[conv_id].append(ChatMessage(role="user", content=request.message))
    
    try:
        # Try to connect to OmniMind backdoor
        from greenlight.omni_mind.backdoor import BackdoorClient
        client = BackdoorClient()
        
        # Send message to OmniMind
        response = client.chat(request.message, project_path=request.project_path)
        assistant_message = response.get("response", "I couldn't process that request.")
        
    except ImportError:
        # OmniMind not available, return placeholder
        assistant_message = "OmniMind is not currently available. Please ensure the backend is running."
    except Exception as e:
        assistant_message = f"Error communicating with OmniMind: {str(e)}"
    
    # Add assistant message
    conversations[conv_id].append(ChatMessage(role="assistant", content=assistant_message))
    
    return ChatResponse(message=assistant_message, conversation_id=conv_id)


@router.get("/{conversation_id}", response_model=list[ChatMessage])
async def get_conversation(conversation_id: str):
    """Get conversation history."""
    if conversation_id not in conversations:
        return []
    return conversations[conversation_id]


@router.delete("/{conversation_id}")
async def clear_conversation(conversation_id: str):
    """Clear a conversation."""
    if conversation_id in conversations:
        del conversations[conversation_id]
    return {"success": True}

