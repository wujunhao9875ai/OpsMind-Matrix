"""设备操作日志表"""
import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, DateTime, ForeignKey, Text, Float, Date
from app.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class DeviceLog(Base):
    __tablename__ = "device_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False, comment="操作类型")
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="变更前状态")
    to_status: Mapped[str | None] = mapped_column(String(50), nullable=True, comment="变更后状态")
    operator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, comment="操作人")
    related_ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, comment="关联工单")
    repair_vendor: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="维修商")
    repair_cost: Mapped[float | None] = mapped_column(Float, nullable=True, comment="维修费用")
    expected_return_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="预计返还日期")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    device: Mapped["Device"] = relationship("Device", back_populates="logs")