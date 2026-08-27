from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List


class MaterialCreate(BaseModel):
    source_conversation_id: Optional[str] = Field(None, max_length=100)
    source_knowledge_id: Optional[str] = Field(None, max_length=100)
    question: str
    answer: str
    material_type: str = Field(..., description="qa_pair, variant, exam_question, negative_sample")
    quality_score: Optional[float] = None
    tags: Optional[List[str]] = None
    difficulty: str = "easy"


class MaterialResponse(BaseModel):
    id: str
    source_conversation_id: Optional[str]
    source_knowledge_id: Optional[str]
    question: str
    answer: str
    material_type: str
    quality_score: Optional[float]
    human_reviewed: bool
    human_approved: Optional[bool]
    review_comment: Optional[str]
    tags: Optional[list]
    difficulty: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True