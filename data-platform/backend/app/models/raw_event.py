from sqlalchemy import Column, String, DateTime, JSON
from app.compat import UUID
from app.database import Base
import uuid
from datetime import datetime


class RawEvent(Base):
    __tablename__ = "raw_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id = Column(String(100), unique=True, index=True)
    source_agent = Column(String(50), index=True)
    event_type = Column(String(50))
    timestamp = Column(DateTime, default=lambda: datetime.utcnow())
    trace_id = Column(String(100), index=True)
    user_id = Column(String(100))
    payload = Column(JSON)
    event_metadata = Column("metadata", JSON)