"""设备表"""
import uuid
from datetime import datetime, timezone, date
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, Float, Date
from app.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True, comment="设备编码")
    serial_number: Mapped[str | None] = mapped_column(String(200), unique=True, nullable=True, index=True, comment="序列号")
    name: Mapped[str] = mapped_column(String(300), nullable=False, comment="设备名称")
    model: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="型号")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="other", index=True, comment="设备类别")
    brand: Mapped[str | None] = mapped_column(String(100), nullable=True, comment="品牌")
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="in_stock", index=True, comment="生命周期状态")
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouse_locations.id"), nullable=True, index=True, comment="当前所在库房")
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True, comment="购入日期")
    warranty_expiry: Mapped[date | None] = mapped_column(Date, nullable=True, comment="保修到期日")
    purchase_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="购入价格")
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="供应商")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本号")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    logs: Mapped[list["DeviceLog"]] = relationship("DeviceLog", back_populates="device", order_by="DeviceLog.created_at", cascade="all, delete-orphan")