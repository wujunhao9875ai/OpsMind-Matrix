import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from app.db_compat import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PreTicket(Base):
    __tablename__ = "pre_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    fault_category: Mapped[str] = mapped_column(String(50), nullable=False)
    urgency: Mapped[str] = mapped_column(String(50), default="medium")
    device_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))