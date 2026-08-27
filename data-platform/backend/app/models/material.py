from sqlalchemy import Column, String, DateTime, Boolean, JSON, Float, Text
from app.compat import UUID
from app.database import Base
import uuid
from datetime import datetime


class Material(Base):
    __tablename__ = "materials"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_conversation_id = Column(String(100))
    source_knowledge_id = Column(String(100))
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    material_type = Column(String(50), nullable=False)  # qa_pair, variant, exam_question, negative_sample
    quality_score = Column(Float)
    human_reviewed = Column(Boolean, default=False)
    human_approved = Column(Boolean)
    review_comment = Column(Text)
    tags = Column(JSON)
    difficulty = Column(String(50), default="easy")
    created_at = Column(DateTime, default=lambda: datetime.utcnow())
    updated_at = Column(DateTime, default=lambda: datetime.utcnow(), onupdate=lambda: datetime.utcnow())