"""库房/库位表"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text
from app.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class WarehouseLocation(Base):
    __tablename__ = "warehouse_locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="库房名称")
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True, comment="库房编码")
    address: Mapped[str | None] = mapped_column(String(500), nullable=True, comment="物理地址")
    manager_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, comment="库管员")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="active", comment="active/inactive")
    description: Mapped[str | None] = mapped_column(Text, nullable=True, comment="描述")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))