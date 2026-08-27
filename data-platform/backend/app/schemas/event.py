from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


class EventCreate(BaseModel):
    event_id: str = Field(..., max_length=100)
    source_agent: str = Field(..., max_length=50)
    event_type: str = Field(..., max_length=50)
    trace_id: Optional[str] = Field(None, max_length=100)
    user_id: Optional[str] = Field(None, max_length=100)
    payload: Optional[dict] = None
    metadata: Optional[dict] = None


class EventResponse(BaseModel):
    id: str
    event_id: str
    source_agent: str
    event_type: str
    timestamp: datetime
    trace_id: Optional[str]
    user_id: Optional[str]
    payload: Optional[Any]
    metadata: Optional[Any]

    class Config:
        from_attributes = True