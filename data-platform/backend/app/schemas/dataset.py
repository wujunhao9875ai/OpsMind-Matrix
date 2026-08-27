from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Any


class DatasetExportRequest(BaseModel):
    dataset_type: str = Field(default="qa", description="qa, classification, ticket")
    format: str = Field(default="jsonl", description="jsonl, csv")
    split: str = Field(default="train", description="train, val, test")
    size: int = Field(default=1000, ge=1, le=100000)


class DatasetResponse(BaseModel):
    dataset_id: str
    dataset_type: str
    format: str
    split: str
    record_count: int
    file_url: str
    metadata: Optional[Any] = None
    created_at: datetime

    class Config:
        from_attributes = True