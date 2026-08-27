import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text
from app.compat import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    pre_ticket_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    conversation_id: Mapped[str | None] = mapped_column(String(50), nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fault_category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    urgency: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    device_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact: Mapped[str | None] = mapped_column(String(128), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created", index=True)
    assigned_to: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    corrected: Mapped[bool] = mapped_column(default=False)

    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))