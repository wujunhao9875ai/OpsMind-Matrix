from pydantic import BaseModel
from datetime import datetime


class ChatHistoryItem(BaseModel):
    id: str
    role: str
    content: str
    msg_type: str = "text"
    category: str | None = None
    confidence: float | None = None
    sources: list | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True