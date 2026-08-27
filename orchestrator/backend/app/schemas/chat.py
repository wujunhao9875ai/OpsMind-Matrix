from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class ChatMessage(BaseModel):
    message: str
    conversation_id: Optional[str] = None


class ChatReply(BaseModel):
    type: str
    data: Optional[dict] = None
    message: Optional[str] = None
    intent: Optional[str] = None
    agent: Optional[str] = None