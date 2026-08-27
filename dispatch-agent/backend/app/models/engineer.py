import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Integer, Float
from app.compat import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class EngineerProfile(Base):
    __tablename__ = "engineer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    skill_levels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="offline", index=True)
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_concurrent: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    current_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_resolution_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))