"""库存乐观锁 + 阈值检查

库存扣减采用 version 字段乐观锁防止并发超发。
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction


class InventoryConcurrentError(Exception):
    """库存并发冲突"""
    pass


class InventoryInsufficientError(Exception):
    """库存不足"""
    pass


MAX_RETRY = 3


async def stock_in(
    db: AsyncSession,
    inventory_id: uuid.UUID,
    quantity: int,
    operator_id: uuid.UUID,
    unit_price: Optional[float] = None,
    comment: Optional[str] = None,
) -> Inventory:
    """入库：增加库存数量"""
    for attempt in range(MAX_RETRY):
        result = await db.execute(
            select(Inventory).where(Inventory.id == inventory_id)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise ValueError(f"库存物品不存在: {inventory_id}")

        quantity_before = inv.quantity
        new_quantity = quantity_before + quantity
        new_available = inv.available_quantity + quantity

        values = {
            "quantity": new_quantity,
            "available_quantity": new_available,
            "version": inv.version + 1,
            "last_restock_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
        }
        if unit_price is not None:
            values["unit_price"] = unit_price

        update_result = await db.execute(
            update(Inventory)
            .where(Inventory.id == inventory_id, Inventory.version == inv.version)
            .values(**values)
        )
        if update_result.rowcount == 0:
            if attempt < MAX_RETRY - 1:
                continue
            raise InventoryConcurrentError("入库并发冲突，请重试")

        # 记录流水
        txn = InventoryTransaction(
            inventory_id=inventory_id,
            transaction_type="stock_in",
            quantity_change=quantity,
            quantity_before=quantity_before,
            quantity_after=new_quantity,
            operator_id=operator_id,
            comment=comment or "入库",
        )
        db.add(txn)
        await db.commit()
        await db.refresh(inv)
        return inv

    raise InventoryConcurrentError("入库并发冲突，请重试")


async def stock_out(
    db: AsyncSession,
    inventory_id: uuid.UUID,
    quantity: int,
    operator_id: uuid.UUID,
    related_ticket_id: Optional[uuid.UUID] = None,
    comment: Optional[str] = None,
) -> Inventory:
    """出库：扣减库存数量"""
    for attempt in range(MAX_RETRY):
        result = await db.execute(
            select(Inventory).where(Inventory.id == inventory_id)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise ValueError(f"库存物品不存在: {inventory_id}")

        if inv.available_quantity < quantity:
            raise InventoryInsufficientError(
                f"库存不足: {inv.name} 可用 {inv.available_quantity}，需要 {quantity}"
            )

        quantity_before = inv.quantity
        new_quantity = quantity_before - quantity
        new_available = inv.available_quantity - quantity

        update_result = await db.execute(
            update(Inventory)
            .where(Inventory.id == inventory_id, Inventory.version == inv.version)
            .values(
                quantity=new_quantity,
                available_quantity=new_available,
                version=inv.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if update_result.rowcount == 0:
            if attempt < MAX_RETRY - 1:
                continue
            raise InventoryConcurrentError("出库并发冲突，请重试")

        txn = InventoryTransaction(
            inventory_id=inventory_id,
            transaction_type="stock_out",
            quantity_change=-quantity,
            quantity_before=quantity_before,
            quantity_after=new_quantity,
            related_ticket_id=related_ticket_id,
            operator_id=operator_id,
            comment=comment or "出库",
        )
        db.add(txn)
        await db.commit()
        await db.refresh(inv)
        return inv

    raise InventoryConcurrentError("出库并发冲突，请重试")


async def allocate_inventory(
    db: AsyncSession,
    inventory_id: uuid.UUID,
    quantity: int,
    operator_id: uuid.UUID,
    related_ticket_id: Optional[uuid.UUID] = None,
    comment: Optional[str] = None,
) -> Inventory:
    """分配库存（减少可用数量，不减少总量）"""
    for attempt in range(MAX_RETRY):
        result = await db.execute(
            select(Inventory).where(Inventory.id == inventory_id)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise ValueError(f"库存物品不存在: {inventory_id}")

        if inv.available_quantity < quantity:
            raise InventoryInsufficientError(
                f"库存不足: {inv.name} 可用 {inv.available_quantity}，需要 {quantity}"
            )

        quantity_before = inv.available_quantity
        new_available = quantity_before - quantity

        update_result = await db.execute(
            update(Inventory)
            .where(Inventory.id == inventory_id, Inventory.version == inv.version)
            .values(
                available_quantity=new_available,
                version=inv.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if update_result.rowcount == 0:
            if attempt < MAX_RETRY - 1:
                continue
            raise InventoryConcurrentError("分配库存并发冲突，请重试")

        txn = InventoryTransaction(
            inventory_id=inventory_id,
            transaction_type="allocate",
            quantity_change=0,
            quantity_before=quantity_before,
            quantity_after=new_available,
            related_ticket_id=related_ticket_id,
            operator_id=operator_id,
            comment=comment or f"分配 {quantity} 个给工单",
        )
        db.add(txn)
        await db.commit()
        await db.refresh(inv)
        return inv

    raise InventoryConcurrentError("分配库存并发冲突，请重试")


async def adjust_inventory(
    db: AsyncSession,
    inventory_id: uuid.UUID,
    new_quantity: int,
    operator_id: uuid.UUID,
    comment: str,
) -> Inventory:
    """库存调整（盘点用），comment 必填"""
    for attempt in range(MAX_RETRY):
        result = await db.execute(
            select(Inventory).where(Inventory.id == inventory_id)
        )
        inv = result.scalar_one_or_none()
        if not inv:
            raise ValueError(f"库存物品不存在: {inventory_id}")

        quantity_before = inv.quantity
        diff = new_quantity - quantity_before

        update_result = await db.execute(
            update(Inventory)
            .where(Inventory.id == inventory_id, Inventory.version == inv.version)
            .values(
                quantity=new_quantity,
                available_quantity=new_quantity,
                version=inv.version + 1,
                updated_at=datetime.now(timezone.utc),
            )
        )
        if update_result.rowcount == 0:
            if attempt < MAX_RETRY - 1:
                continue
            raise InventoryConcurrentError("库存调整并发冲突，请重试")

        txn = InventoryTransaction(
            inventory_id=inventory_id,
            transaction_type="adjust",
            quantity_change=diff,
            quantity_before=quantity_before,
            quantity_after=new_quantity,
            operator_id=operator_id,
            comment=comment,
        )
        db.add(txn)
        await db.commit()
        await db.refresh(inv)
        return inv

    raise InventoryConcurrentError("库存调整并发冲突，请重试")


def check_low_stock(inventory: Inventory) -> bool:
    """检查是否低库存"""
    return inventory.quantity <= inventory.min_threshold


def check_out_of_stock(inventory: Inventory) -> bool:
    """检查是否库存耗尽"""
    return inventory.quantity == 0


def check_idle(inventory: Inventory, days: int = 180) -> bool:
    """检查是否呆滞（超过指定天数未入库）"""
    if inventory.last_restock_at is None:
        return False
    delta = datetime.now(timezone.utc) - inventory.last_restock_at
    return delta.days > days