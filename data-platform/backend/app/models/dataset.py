from sqlalchemy import Column, String, DateTime, Integer, JSON, Text
from app.compat import UUID
from app.database import Base
import uuid
from datetime import datetime, timezone


class Dataset(Base):
    __tablename__ = "datasets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dataset_id = Column(String(100), unique=True, index=True)
    dataset_type = Column(String(50))  # qa, classification, ticket
    format = Column(String(20))  # jsonl, csv
    split = Column(String(20))  # train, val, test
    record_count = Column(Integer)
    file_url = Column(String(500))
    dataset_metadata = Column("metadata", JSON)
    created_at = Column(DateTime, default=lambda: datetime.utcnow())