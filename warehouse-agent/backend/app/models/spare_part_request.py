"""备件申请表"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, Text, Integer
from app.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class SparePartRequest(Base):
    __tablename__ = "spare_part_requests"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True, comment="关联工单ID")
    inventory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, comment="匹配的库存物品")
    item_name: Mapped[str] = mapped_column(String(300), nullable=False, comment="申请的物品名称")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="申请数量")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending", index=True, comment="状态")
    requested_by: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="申请人")
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="批准人")
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="备货完成时间")
    rejected_reason: Mapped[str | None] = mapped_column(Text, nullable=True, comment="拒绝原因")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))