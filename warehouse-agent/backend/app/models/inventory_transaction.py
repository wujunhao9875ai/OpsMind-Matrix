"""库存流水表"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer
from app.compat import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class InventoryTransaction(Base):
    __tablename__ = "inventory_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("inventory.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True, comment="操作类型")
    quantity_change: Mapped[int] = mapped_column(Integer, nullable=False, comment="数量变化")
    quantity_before: Mapped[int] = mapped_column(Integer, nullable=False, comment="操作前数量")
    quantity_after: Mapped[int] = mapped_column(Integer, nullable=False, comment="操作后数量")
    related_ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True, comment="关联工单")
    related_device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, comment="关联设备")
    from_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouse_locations.id"), nullable=True, comment="调出库房")
    to_location_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("warehouse_locations.id"), nullable=True, comment="调入库房")
    operator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, comment="操作人")
    comment: Mapped[str | None] = mapped_column(Text, nullable=True, comment="备注")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    inventory: Mapped["Inventory"] = relationship("Inventory", back_populates="transactions")