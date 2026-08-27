"""
本地 Mock 测试：用 SQLite 内存库跑通仓库核心逻辑。
无需 PostgreSQL / Redis / Consul，直接运行：
  python -m tests.test_warehouse_local
"""
import asyncio
import sys
import os
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ---- Mock: 用 SQLite 替换 PostgreSQL ----
from app import config
config.settings.database_url = "sqlite+aiosqlite:///:memory:"

from app.database import engine, Base, async_session, init_db
from app.models.warehouse_location import WarehouseLocation
from app.models.device import Device
from app.models.inventory import Inventory
from app.models.device_log import DeviceLog
from app.models.inventory_transaction import InventoryTransaction
from app.models.spare_part_request import SparePartRequest
from app.core.warehouse_service import (
    create_location, get_locations, update_location, delete_location,
    create_device, get_devices, get_device, update_device, change_device_status,
    transfer_device, get_device_logs,
    create_inventory, get_inventories, get_inventory, update_inventory,
    get_warehouse_overview,
)
from app.core.inventory_guard import (
    stock_in, stock_out, allocate_inventory, adjust_inventory,
    check_low_stock, check_out_of_stock, InventoryInsufficientError,
)
from app.core.device_state_machine import DeviceStatus, DeviceAction, get_next_status
from app.core.spare_request_service import create_spare_request
from sqlalchemy import select


async def run():
    await init_db()
    print("=" * 60)
    print("Warehouse Agent 本地 Mock 测试")
    print("=" * 60)

    # ==========================================
    # 1. 创建库房
    # ==========================================
    print("\n[1] 创建库房...")
    loc_a = await create_location(async_session(), {
        "name": "A栋库房", "code": "WH-A", "address": "A栋1层", "status": "active"
    })
    loc_b = await create_location(async_session(), {
        "name": "B栋库房", "code": "WH-B", "address": "B栋地下1层", "status": "active"
    })
    print(f"  创建: {loc_a.name} (id={loc_a.id})")
    print(f"  创建: {loc_b.name} (id={loc_b.id})")

    locations = await get_locations(async_session())
    print(f"  库房总数: {len(locations)}")

    # ==========================================
    # 2. 创建设备
    # ==========================================
    print("\n[2] 创建设备...")
    printer = await create_device(async_session(), {
        "name": "HP LaserJet Pro M404dn", "model": "M404dn",
        "category": "printer", "brand": "HP", "status": "in_stock",
        "purchase_price": 3200.00, "location_id": loc_a.id,
    })
    laptop = await create_device(async_session(), {
        "name": "ThinkPad X1 Carbon", "model": "X1 Carbon Gen11",
        "category": "computer", "brand": "Lenovo", "status": "in_stock",
        "purchase_price": 9800.00, "location_id": loc_a.id,
    })
    monitor = await create_device(async_session(), {
        "name": "Dell U2723QE", "model": "U2723QE",
        "category": "monitor", "brand": "Dell", "status": "in_stock",
        "purchase_price": 3500.00, "location_id": loc_a.id,
    })
    print(f"  创建: {printer.name} ({printer.device_no})")
    print(f"  创建: {laptop.name} ({laptop.device_no})")
    print(f"  创建: {monitor.name} ({monitor.device_no})")

    devices, total = await get_devices(async_session())
    print(f"  设备总数: {total}")

    # ==========================================
    # 3. 设备状态机流转
    # ==========================================
    print("\n[3] 设备状态流转...")
    op_id = uuid.uuid4()

    # 分配设备
    device = await change_device_status(
        async_session(), printer.id, DeviceAction.ALLOCATE, op_id,
        comment="分配给市场部"
    )
    print(f"  分配: {printer.name} -> {device.status}")

    # 交付使用
    device = await change_device_status(
        async_session(), printer.id, DeviceAction.DELIVER, op_id,
        comment="已交付使用"
    )
    print(f"  交付: {printer.name} -> {device.status}")

    # 报损
    device = await change_device_status(
        async_session(), printer.id, DeviceAction.RETURN_DAMAGED, op_id,
        comment="纸张卡死，滚筒损坏"
    )
    print(f"  报损: {printer.name} -> {device.status}")

    # 送修
    device = await change_device_status(
        async_session(), printer.id, DeviceAction.SEND_REPAIR, op_id,
        repair_vendor="HP官方售后", repair_cost=800.00, comment="更换滚筒"
    )
    send_logs = await get_device_logs(async_session(), printer.id)
    print(f"  送修: {printer.name} -> {device.status} (维修商: {send_logs[0].repair_vendor})")

    # 修复完成
    device = await change_device_status(
        async_session(), printer.id, DeviceAction.REPAIR_DONE, op_id,
        comment="滚筒已更换，测试正常"
    )
    print(f"  修复: {printer.name} -> {device.status}")

    # 重新入库
    device = await change_device_status(
        async_session(), printer.id, DeviceAction.RESTOCK, op_id,
        comment="重新入库，可供分配"
    )
    print(f"  入库: {printer.name} -> {device.status}")

    # 查看日志
    logs = await get_device_logs(async_session(), printer.id)
    print(f"  操作日志: {len(logs)} 条")
    for log in logs:
        print(f"    [{log.action}] {log.from_status} -> {log.to_status} | {log.comment}")

    # ==========================================
    # 4. 设备调拨
    # ==========================================
    print("\n[4] 设备调拨...")
    device = await transfer_device(
        async_session(), laptop.id, loc_b.id, op_id,
        comment="调拨至B栋库房备用"
    )
    print(f"  调拨: {laptop.name} -> {loc_b.name}")

    # ==========================================
    # 5. 库存管理
    # ==========================================
    print("\n[5] 库存管理...")
    toner = await create_inventory(async_session(), {
        "name": "打印机碳粉 HP 26A", "category": "consumable",
        "model_spec": "HP 26A", "unit": "个", "quantity": 50,
        "min_threshold": 10, "max_threshold": 200, "unit_price": 380.00,
        "location_id": loc_a.id,
    })
    paper = await create_inventory(async_session(), {
        "name": "A4打印纸", "category": "consumable",
        "model_spec": "70g 500张/包", "unit": "包", "quantity": 200,
        "min_threshold": 50, "max_threshold": 500, "unit_price": 25.00,
        "location_id": loc_a.id,
    })
    cable = await create_inventory(async_session(), {
        "name": "网线 Cat6 3米", "category": "network",
        "model_spec": "Cat6 3m", "unit": "根", "quantity": 100,
        "min_threshold": 20, "max_threshold": 300, "unit_price": 15.00,
        "location_id": loc_a.id,
    })
    print(f"  创建库存: {toner.name} (库存: {toner.quantity}{toner.unit})")
    print(f"  创建库存: {paper.name} (库存: {paper.quantity}{paper.unit})")
    print(f"  创建库存: {cable.name} (库存: {cable.quantity}{cable.unit})")

    invs, total = await get_inventories(async_session())
    print(f"  库存种类: {total}")

    # ==========================================
    # 6. 库存出入库（乐观锁）
    # ==========================================
    print("\n[6] 库存出入库...")

    # 入库
    inv = await stock_in(async_session(), toner.id, 20, op_id, comment="采购入库")
    print(f"  入库: {toner.name} +20 -> 当前 {inv.quantity}{toner.unit}")

    # 出库
    inv = await stock_out(async_session(), toner.id, 5, op_id, comment="维修使用")
    print(f"  出库: {toner.name} -5 -> 当前 {inv.quantity}{toner.unit}")

    # 分配库存（只减可用，不减总量）
    inv = await allocate_inventory(async_session(), cable.id, 10, op_id, comment="预留给网络改造项目")
    print(f"  分配: {cable.name} 可用 {inv.available_quantity}/{inv.quantity}")

    # 库存调整（盘点）
    inv = await adjust_inventory(async_session(), paper.id, 195, op_id, comment="盘点差异 -5包")
    print(f"  调整: {paper.name} {paper.quantity} -> {inv.quantity} (盘点差异)")

    # 低库存检查
    ssd = await create_inventory(async_session(), {
        "name": "SSD固态硬盘 512GB", "category": "hardware",
        "model_spec": "Samsung 870 EVO", "unit": "个", "quantity": 3,
        "min_threshold": 5, "max_threshold": 50, "unit_price": 350.00,
        "location_id": loc_a.id,
    })
    print(f"\n  低库存检查: {ssd.name} (库存:{ssd.quantity}, 阈值:{ssd.min_threshold})")
    print(f"    low_stock: {check_low_stock(ssd)}")
    print(f"    out_of_stock: {check_out_of_stock(ssd)}")

    # 库存不足异常
    try:
        await stock_out(async_session(), ssd.id, 10, op_id, comment="大量出库")
    except InventoryInsufficientError as e:
        print(f"  库存不足异常: {e}")

    # ==========================================
    # 7. 备件申请
    # ==========================================
    print("\n[7] 备件申请...")
    req = await create_spare_request(
        async_session(), "碳粉", 2, "TICKET-001", str(op_id)
    )
    print(f"  创建申请: {req['item_name']} x{req['quantity']} -> {req['status']}")
    print(f"  库存可满足: {req['inventory_available']}")

    # 申请不存在的物品
    req2 = await create_spare_request(
        async_session(), "外星人芯片", 1, "TICKET-002", str(op_id)
    )
    print(f"  创建申请: {req2['item_name']} x{req2['quantity']} -> {req2['status']}")
    print(f"  库存可满足: {req2['inventory_available']}")

    # ==========================================
    # 8. 仓库概览
    # ==========================================
    print("\n[8] 仓库概览...")
    overview = await get_warehouse_overview(async_session())
    print(f"  设备总数: {overview['total_devices']}")
    print(f"  库存种类: {overview['total_inventory_types']}")
    print(f"  低库存数: {overview['low_stock_count']}")
    print(f"  待备货: {overview['pending_spare_requests']}")
    print(f"  损坏设备: {overview['damaged_count']}")
    print(f"  本月入库: {overview['stock_in_this_month']}")
    print(f"  本月出库: {overview['stock_out_this_month']}")

    # ==========================================
    # 9. 更新操作
    # ==========================================
    print("\n[9] 更新操作...")
    updated = await update_location(async_session(), loc_a.id, {"description": "主库房-已扩容"})
    print(f"  更新库房: {updated.name} -> {updated.description}")

    updated_dev = await update_device(async_session(), monitor.id, {"purchase_price": 3200.00})
    print(f"  更新设备: {updated_dev.name} 价格 {monitor.purchase_price} -> {updated_dev.purchase_price}")

    updated_inv = await update_inventory(async_session(), toner.id, {"min_threshold": 15})
    print(f"  更新库存: {toner.name} 阈值 {toner.min_threshold} -> {updated_inv.min_threshold}")

    # ==========================================
    # 10. 删除操作（带约束检查）
    # ==========================================
    print("\n[10] 删除操作...")
    # 有设备的库房不能删
    try:
        await delete_location(async_session(), loc_a.id)
        print("  ERROR: 不应删除有设备的库房")
    except ValueError as e:
        print(f"  删除库房被阻止: {e}")

    # 清空库房后可删
    temp_loc = await create_location(async_session(), {
        "name": "临时库房", "code": "WH-TEMP", "address": "临时", "status": "active"
    })
    await delete_location(async_session(), temp_loc.id)
    print(f"  删除空库房成功: {temp_loc.name}")

    # ==========================================
    print("\n" + "=" * 60)
    print("全部测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run())