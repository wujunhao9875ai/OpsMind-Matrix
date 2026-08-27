"""库存表（耗材类物品）"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer, Float
from app.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Inventory(Base):
    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(300), nullable=False, index=True, comment="物品名称")
    category: Mapped[str] = mapped_column(String(50), nullable=False, default="consumable", index=True, comment="类别")
    model_spec: Mapped[str | None] = mapped_column(String(200), nullable=True, comment="型号规格")
    unit: Mapped[str] = mapped_column(String(50), nullable=False, default="个", comment="单位")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="当前库存数量")
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="可用数量")
    min_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=5, comment="最低库存阈值")
    max_threshold: Mapped[int] = mapped_column(Integer, nullable=False, default=100, comment="最高库存阈值")
    location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouse_locations.id"), nullable=True, index=True, comment="所在库房")
    unit_price: Mapped[float | None] = mapped_column(Float, nullable=True, comment="单价")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="乐观锁版本号")
    last_restock_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, comment="最近入库时间")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    transactions: Mapped[list["InventoryTransaction"]] = relationship("InventoryTransaction", back_populates="inventory", order_by="InventoryTransaction.created_at", cascade="all, delete-orphan")