"""库房核心业务逻辑"""
import uuid
from datetime import datetime, timezone, date
from typing import Optional
from sqlalchemy import select, func, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from app.models.warehouse_location import WarehouseLocation
from app.models.device import Device
from app.models.device_log import DeviceLog
from app.models.inventory import Inventory
from app.models.inventory_transaction import InventoryTransaction
from app.models.spare_part_request import SparePartRequest
from app.core.device_state_machine import (
    get_next_status, build_device_log, DeviceStatus, TERMINAL_STATES
)
from app.core.inventory_guard import (
    stock_in, stock_out, allocate_inventory, adjust_inventory,
    check_low_stock, check_out_of_stock,
    InventoryConcurrentError, InventoryInsufficientError,
)


def _generate_device_no(category: str) -> str:
    """生成设备编码 DEV-{category}-{YYYYMMDD}-{NNNN}"""
    import random
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    short = category[:8].upper()
    seq = random.randint(1, 9999)
    return f"DEV-{short}-{date_part}-{seq:04d}"


# ---- Warehouse Location ----
async def get_locations(db: AsyncSession) -> list[WarehouseLocation]:
    result = await db.execute(select(WarehouseLocation))
    return list(result.scalars().all())


async def create_location(db: AsyncSession, data: dict) -> WarehouseLocation:
    loc = WarehouseLocation(**data)
    db.add(loc)
    await db.commit()
    await db.refresh(loc)
    return loc


async def update_location(db: AsyncSession, loc_id: uuid.UUID, data: dict) -> WarehouseLocation:
    result = await db.execute(select(WarehouseLocation).where(WarehouseLocation.id == loc_id))
    loc = result.scalar_one_or_none()
    if not loc:
        raise ValueError(f"库房不存在: {loc_id}")
    allowed_fields = {"name", "address", "manager_id", "status", "description"}
    for key, value in data.items():
        if value is not None and key in allowed_fields:
            setattr(loc, key, value)
    loc.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(loc)
    return loc


async def delete_location(db: AsyncSession, loc_id: uuid.UUID) -> None:
    result = await db.execute(select(WarehouseLocation).where(WarehouseLocation.id == loc_id))
    loc = result.scalar_one_or_none()
    if not loc:
        raise ValueError(f"库房不存在: {loc_id}")
    # 检查是否有设备关联
    dev_result = await db.execute(
        select(func.count(Device.id)).where(Device.location_id == loc_id)
    )
    dev_count = dev_result.scalar()
    if dev_count > 0:
        raise ValueError(f"库房下有 {dev_count} 台设备，请先转移设备后再删除")
    await db.delete(loc)
    await db.commit()


# ---- Device ----
async def get_devices(
    db: AsyncSession, page: int = 1, page_size: int = 20,
    status: Optional[str] = None, category: Optional[str] = None,
    location_id: Optional[uuid.UUID] = None, search: Optional[str] = None,
) -> tuple[list[Device], int]:
    query = select(Device)
    count_query = select(func.count(Device.id))

    if status:
        query = query.where(Device.status == status)
        count_query = count_query.where(Device.status == status)
    if category:
        query = query.where(Device.category == category)
        count_query = count_query.where(Device.category == category)
    if location_id:
        query = query.where(Device.location_id == location_id)
        count_query = count_query.where(Device.location_id == location_id)
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Device.name.ilike(search_term)) |
            (Device.serial_number.ilike(search_term)) |
            (Device.device_no.ilike(search_term)) |
            (Device.model.ilike(search_term))
        )
        count_query = count_query.where(
            (Device.name.ilike(search_term)) |
            (Device.serial_number.ilike(search_term)) |
            (Device.device_no.ilike(search_term)) |
            (Device.model.ilike(search_term))
        )

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(desc(Device.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())
    return items, total


async def get_device(db: AsyncSession, device_id: uuid.UUID) -> Optional[Device]:
    result = await db.execute(
        select(Device).where(Device.id == device_id).options(selectinload(Device.logs))
    )
    return result.scalar_one_or_none()


async def create_device(db: AsyncSession, data: dict) -> Device:
    device_no = _generate_device_no(data.get("category", "other"))
    device = Device(device_no=device_no, **data)
    db.add(device)
    await db.commit()
    await db.refresh(device)
    return device


async def update_device(db: AsyncSession, device_id: uuid.UUID, data: dict) -> Device:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise ValueError(f"设备不存在: {device_id}")
    for key, value in data.items():
        if value is not None:
            setattr(device, key, value)
    device.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(device)
    return device


async def change_device_status(
    db: AsyncSession, device_id: uuid.UUID, action: str, operator_id: uuid.UUID,
    related_ticket_id: Optional[uuid.UUID] = None,
    repair_vendor: Optional[str] = None, repair_cost: Optional[float] = None,
    expected_return_date: Optional[date] = None, comment: Optional[str] = None,
) -> Device:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise ValueError(f"设备不存在: {device_id}")

    from_status = device.status
    to_status = get_next_status(from_status, action)

    # 状态变更副作用
    device.status = to_status
    device.updated_at = datetime.now(timezone.utc)

    # 记录日志
    log_data = build_device_log(
        device_id=device_id, action=action, from_status=from_status,
        to_status=to_status, operator_id=operator_id,
        related_ticket_id=related_ticket_id, repair_vendor=repair_vendor,
        repair_cost=repair_cost, expected_return_date=expected_return_date,
        comment=comment,
    )
    device_log = DeviceLog(**log_data)
    db.add(device_log)
    await db.commit()
    await db.refresh(device)
    return device


async def transfer_device(
    db: AsyncSession, device_id: uuid.UUID, to_location_id: uuid.UUID,
    operator_id: uuid.UUID, comment: Optional[str] = None,
) -> Device:
    result = await db.execute(select(Device).where(Device.id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        raise ValueError(f"设备不存在: {device_id}")

    device.location_id = to_location_id
    device.updated_at = datetime.now(timezone.utc)

    log = DeviceLog(
        device_id=device_id,
        action="transfer",
        from_status=device.status,
        to_status=device.status,
        operator_id=operator_id,
        comment=comment or f"调拨至 {to_location_id}",
    )
    db.add(log)
    await db.commit()
    await db.refresh(device)
    return device


async def get_device_logs(db: AsyncSession, device_id: uuid.UUID) -> list[DeviceLog]:
    result = await db.execute(
        select(DeviceLog).where(DeviceLog.device_id == device_id).order_by(desc(DeviceLog.created_at))
    )
    return list(result.scalars().all())


# ---- Inventory ----
async def get_inventories(
    db: AsyncSession, page: int = 1, page_size: int = 20,
    category: Optional[str] = None, location_id: Optional[uuid.UUID] = None,
    search: Optional[str] = None, low_stock_only: bool = False,
) -> tuple[list[Inventory], int]:
    query = select(Inventory)
    count_query = select(func.count(Inventory.id))

    if category:
        query = query.where(Inventory.category == category)
        count_query = count_query.where(Inventory.category == category)
    if location_id:
        query = query.where(Inventory.location_id == location_id)
        count_query = count_query.where(Inventory.location_id == location_id)
    if search:
        search_term = f"%{search}%"
        query = query.where(
            (Inventory.name.ilike(search_term)) |
            (Inventory.model_spec.ilike(search_term))
        )
        count_query = count_query.where(
            (Inventory.name.ilike(search_term)) |
            (Inventory.model_spec.ilike(search_term))
        )
    if low_stock_only:
        query = query.where(Inventory.quantity <= Inventory.min_threshold)
        count_query = count_query.where(Inventory.quantity <= Inventory.min_threshold)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(desc(Inventory.updated_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())
    return items, total


async def get_inventory(db: AsyncSession, inv_id: uuid.UUID) -> Optional[Inventory]:
    result = await db.execute(
        select(Inventory).where(Inventory.id == inv_id).options(selectinload(Inventory.transactions))
    )
    return result.scalar_one_or_none()


async def create_inventory(db: AsyncSession, data: dict) -> Inventory:
    if data.get("quantity", 0) > 0:
        data["available_quantity"] = data["quantity"]
    inv = Inventory(**data)
    db.add(inv)
    await db.commit()
    await db.refresh(inv)
    return inv


async def update_inventory(db: AsyncSession, inv_id: uuid.UUID, data: dict) -> Inventory:
    result = await db.execute(select(Inventory).where(Inventory.id == inv_id))
    inv = result.scalar_one_or_none()
    if not inv:
        raise ValueError(f"库存物品不存在: {inv_id}")
    for key, value in data.items():
        if value is not None:
            setattr(inv, key, value)
    inv.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(inv)
    return inv


async def get_inventory_transactions(
    db: AsyncSession, inv_id: uuid.UUID, page: int = 1, page_size: int = 50,
) -> tuple[list[InventoryTransaction], int]:
    count_result = await db.execute(
        select(func.count(InventoryTransaction.id)).where(InventoryTransaction.inventory_id == inv_id)
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        select(InventoryTransaction)
        .where(InventoryTransaction.inventory_id == inv_id)
        .order_by(desc(InventoryTransaction.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    items = list(result.scalars().all())
    return items, total


# ---- Spare Part Request ----
async def get_spare_requests(
    db: AsyncSession, page: int = 1, page_size: int = 20,
    status: Optional[str] = None, ticket_id: Optional[str] = None,
) -> tuple[list[SparePartRequest], int]:
    query = select(SparePartRequest)
    count_query = select(func.count(SparePartRequest.id))

    if status:
        query = query.where(SparePartRequest.status == status)
        count_query = count_query.where(SparePartRequest.status == status)
    if ticket_id:
        query = query.where(SparePartRequest.ticket_id == ticket_id)
        count_query = count_query.where(SparePartRequest.ticket_id == ticket_id)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    query = query.order_by(desc(SparePartRequest.created_at)).offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    items = list(result.scalars().all())
    return items, total


async def approve_spare_request(db: AsyncSession, request_id: uuid.UUID, operator_id: uuid.UUID) -> SparePartRequest:
    result = await db.execute(select(SparePartRequest).where(SparePartRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise ValueError(f"备件申请不存在: {request_id}")
    if req.status != "pending":
        raise ValueError(f"备件申请状态不是 pending: {req.status}")
    req.status = "approved"
    req.approved_by = str(operator_id)
    req.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(req)
    return req


async def reject_spare_request(db: AsyncSession, request_id: uuid.UUID, operator_id: uuid.UUID, reason: str) -> SparePartRequest:
    result = await db.execute(select(SparePartRequest).where(SparePartRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise ValueError(f"备件申请不存在: {request_id}")
    if req.status != "pending":
        raise ValueError(f"备件申请状态不是 pending: {req.status}")
    req.status = "rejected"
    req.approved_by = str(operator_id)
    req.rejected_reason = reason
    req.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(req)
    return req


async def fulfill_spare_request(db: AsyncSession, request_id: uuid.UUID, operator_id: uuid.UUID) -> SparePartRequest:
    result = await db.execute(select(SparePartRequest).where(SparePartRequest.id == request_id))
    req = result.scalar_one_or_none()
    if not req:
        raise ValueError(f"备件申请不存在: {request_id}")
    if req.status not in ("pending", "approved"):
        raise ValueError(f"备件申请状态不允许备货: {req.status}")

    # 扣减库存
    if req.inventory_id:
        await stock_out(
            db, req.inventory_id, req.quantity, operator_id,
            related_ticket_id=None,
            comment=f"备件申请 {req.id} 备货完成",
        )

    req.status = "fulfilled"
    req.fulfilled_at = datetime.now(timezone.utc)
    req.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(req)
    return req


# ---- Stats ----
async def get_warehouse_overview(db: AsyncSession) -> dict:
    # 设备总数
    devices_result = await db.execute(select(func.count(Device.id)))
    total_devices = devices_result.scalar() or 0

    # 库存种类
    inv_result = await db.execute(select(func.count(Inventory.id)))
    total_inventory_types = inv_result.scalar() or 0

    # 低库存
    low_result = await db.execute(
        select(func.count(Inventory.id)).where(Inventory.quantity <= Inventory.min_threshold)
    )
    low_stock_count = low_result.scalar() or 0

    # 待备货
    pending_result = await db.execute(
        select(func.count(SparePartRequest.id)).where(SparePartRequest.status.in_(["pending", "approved"]))
    )
    pending_spare = pending_result.scalar() or 0

    # 损坏设备
    damaged_result = await db.execute(
        select(func.count(Device.id)).where(Device.status == DeviceStatus.DAMAGED)
    )
    damaged_count = damaged_result.scalar() or 0

    # 本月出入库
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    stock_in_result = await db.execute(
        select(func.count(InventoryTransaction.id)).where(
            InventoryTransaction.transaction_type == "stock_in",
            InventoryTransaction.created_at >= month_start,
        )
    )
    stock_out_result = await db.execute(
        select(func.count(InventoryTransaction.id)).where(
            InventoryTransaction.transaction_type == "stock_out",
            InventoryTransaction.created_at >= month_start,
        )
    )

    return {
        "total_devices": total_devices,
        "total_inventory_types": total_inventory_types,
        "low_stock_count": low_stock_count,
        "pending_spare_requests": pending_spare,
        "damaged_count": damaged_count,
        "stock_in_this_month": stock_in_result.scalar() or 0,
        "stock_out_this_month": stock_out_result.scalar() or 0,
    }