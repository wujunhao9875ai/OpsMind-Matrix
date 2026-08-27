"""备件申请服务 - 处理 Dispatch Agent 通过 MCP 发来的备件申请"""
import uuid
from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.spare_part_request import SparePartRequest
from app.models.inventory import Inventory
from app.core.inventory_guard import stock_out


async def create_spare_request(
    db: AsyncSession,
    item_name: str,
    quantity: int,
    ticket_id: str,
    operator_id: str = None,
) -> dict:
    # Find matching inventory item
    result = await db.execute(
        select(Inventory).where(Inventory.name.ilike(f"%{item_name}%"))
    )
    inventory_item = result.scalar_one_or_none()

    request = SparePartRequest(
        item_name=item_name,
        quantity=quantity,
        ticket_id=ticket_id,
        inventory_id=inventory_item.id if inventory_item else None,
        status="pending",
        requested_by=operator_id,
    )
    db.add(request)
    await db.commit()
    await db.refresh(request)

    return {
        "request_id": str(request.id),
        "status": request.status,
        "item_name": item_name,
        "quantity": quantity,
        "inventory_available": inventory_item is not None and inventory_item.quantity >= quantity,
    }