from sqlalchemy import Column, String, DateTime, Float, JSON
from app.compat import UUID
from app.database import Base
import uuid
from datetime import datetime


class AnalyticsCache(Base):
    __tablename__ = "analytics_cache"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    metric_name = Column(String(100), index=True)
    value = Column(Float)
    time_bucket = Column(String(50))
    metric_metadata = Column("metadata", JSON)
    updated_at = Column(DateTime, default=lambda: datetime.utcnow())