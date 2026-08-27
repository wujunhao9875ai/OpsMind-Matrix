"""Warehouse Agent MCP Server - MCP 工具注册

注册 MCP 工具:
  - chat_reply: 统一对话入口（库存查询、设备查询、库房概览等）
  - stock_in: 入库
  - stock_out: 出库
  - device_query: 设备查询
  - ocr_recognize: OCR 铭牌识别
  - spare_request: 备件申请
  - inventory_check: 库存盘点
  - device_status_change: 设备状态变更
  - transfer_device: 设备调拨
  - create_device: 创建设备
  - create_inventory: 创建库存物品
  - get_locations: 获取库房位置列表
  - create_location: 创建库房位置
  - update_location: 更新库房位置
  - delete_location: 删除库房位置
  - warehouse_overview: 库房概览统计
  - device_logs: 设备操作日志
  - inventory_transactions: 库存交易记录
  - spare_requests: 备件申请列表
  - approve_spare: 批准备件申请
  - reject_spare: 拒绝备件申请
  - fulfill_spare: 完成备件申请

注册 3 个 MCP 资源:
  - device://{device_id}: 设备详情
  - inventory://{item_id}: 库存物品详情
  - location://{location_id}: 库房位置详情
"""
import os
import uuid
import json
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import select
from app.database import async_session
from app.models.device import Device
from app.models.inventory import Inventory
from app.models.warehouse_location import WarehouseLocation
from app.core.warehouse_service import (
    get_device, get_devices, get_inventory, get_inventories,
    get_locations, change_device_status, transfer_device,
    get_warehouse_overview, create_device, create_inventory,
    create_location, update_location, delete_location,
    get_device_logs, get_inventory_transactions,
    get_spare_requests, approve_spare_request,
    reject_spare_request, fulfill_spare_request,
)
from app.core.inventory_guard import (
    stock_in, stock_out, adjust_inventory,
    InventoryInsufficientError, InventoryConcurrentError,
)
from app.core.ocr_service import recognize_nameplate
from app.core.spare_request_service import create_spare_request


# ---- MCP Tool Handlers ----

async def handle_stock_in(arguments: dict) -> str:
    """入库操作"""
    inventory_id = uuid.UUID(arguments["inventory_id"])
    quantity = int(arguments["quantity"])
    operator_id = uuid.UUID(arguments.get("operator_id", "00000000-0000-0000-0000-000000000000"))
    unit_price = arguments.get("unit_price")
    comment = arguments.get("comment")

    async with async_session() as db:
        try:
            inv = await stock_in(db, inventory_id, quantity, operator_id, unit_price=unit_price, comment=comment)
            return json.dumps({
                "success": True,
                "inventory_id": str(inv.id),
                "name": inv.name,
                "new_quantity": inv.quantity,
                "available_quantity": inv.available_quantity,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_stock_out(arguments: dict) -> str:
    """出库操作"""
    inventory_id = uuid.UUID(arguments["inventory_id"])
    quantity = int(arguments["quantity"])
    operator_id = uuid.UUID(arguments.get("operator_id", "00000000-0000-0000-0000-000000000000"))
    related_ticket_id = arguments.get("related_ticket_id")
    comment = arguments.get("comment")

    async with async_session() as db:
        try:
            inv = await stock_out(
                db, inventory_id, quantity, operator_id,
                related_ticket_id=uuid.UUID(related_ticket_id) if related_ticket_id else None,
                comment=comment,
            )
            return json.dumps({
                "success": True,
                "inventory_id": str(inv.id),
                "name": inv.name,
                "new_quantity": inv.quantity,
                "available_quantity": inv.available_quantity,
            }, ensure_ascii=False)
        except InventoryInsufficientError as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_device_query(arguments: dict) -> str:
    """设备查询"""
    async with async_session() as db:
        device_id = arguments.get("device_id")
        serial_number = arguments.get("serial_number")
        device_no = arguments.get("device_no")
        status = arguments.get("status")
        search = arguments.get("search")
        page = int(arguments.get("page", 1))
        page_size = int(arguments.get("page_size", 20))

        if device_id:
            device = await get_device(db, uuid.UUID(device_id))
            if device:
                return json.dumps({
                    "id": str(device.id),
                    "device_no": device.device_no,
                    "serial_number": device.serial_number,
                    "name": device.name,
                    "model": device.model,
                    "category": device.category,
                    "brand": device.brand,
                    "status": device.status,
                    "location_id": str(device.location_id) if device.location_id else None,
                    "purchase_date": str(device.purchase_date) if device.purchase_date else None,
                    "warranty_expiry": str(device.warranty_expiry) if device.warranty_expiry else None,
                    "purchase_price": device.purchase_price,
                    "supplier": device.supplier,
                    "notes": device.notes,
                    "created_at": device.created_at.isoformat(),
                    "updated_at": device.updated_at.isoformat(),
                }, ensure_ascii=False)
            return json.dumps({"error": "设备不存在"}, ensure_ascii=False)

        if serial_number:
            result = await db.execute(
                select(Device).where(Device.serial_number == serial_number)
            )
            device = result.scalar_one_or_none()
            if device:
                return json.dumps({
                    "id": str(device.id),
                    "device_no": device.device_no,
                    "serial_number": device.serial_number,
                    "name": device.name,
                    "status": device.status,
                }, ensure_ascii=False)
            return json.dumps({"error": "设备不存在"}, ensure_ascii=False)

        if device_no:
            result = await db.execute(
                select(Device).where(Device.device_no == device_no)
            )
            device = result.scalar_one_or_none()
            if device:
                return json.dumps({
                    "id": str(device.id),
                    "device_no": device.device_no,
                    "serial_number": device.serial_number,
                    "name": device.name,
                    "status": device.status,
                }, ensure_ascii=False)
            return json.dumps({"error": "设备不存在"}, ensure_ascii=False)

        devices, total = await get_devices(
            db, page=page, page_size=page_size,
            status=status, search=search,
        )
        return json.dumps({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": str(d.id),
                    "device_no": d.device_no,
                    "serial_number": d.serial_number,
                    "name": d.name,
                    "model": d.model,
                    "status": d.status,
                    "location_id": str(d.location_id) if d.location_id else None,
                }
                for d in devices
            ],
        }, ensure_ascii=False)


async def handle_ocr_recognize(arguments: dict) -> str:
    """OCR 铭牌识别"""
    image_base64 = arguments.get("image_base64")
    if not image_base64:
        return json.dumps({"error": "缺少 image_base64 参数"}, ensure_ascii=False)

    import base64
    try:
        image_bytes = base64.b64decode(image_base64)
    except Exception:
        return json.dumps({"error": "Base64 解码失败"}, ensure_ascii=False)

    result = recognize_nameplate(image_bytes)
    return json.dumps(result, ensure_ascii=False)


async def handle_spare_request(arguments: dict) -> str:
    """备件申请"""
    item_name = arguments["item_name"]
    quantity = int(arguments["quantity"])
    ticket_id = arguments["ticket_id"]
    operator_id = arguments.get("operator_id")

    async with async_session() as db:
        try:
            result = await create_spare_request(
                db, item_name, quantity, ticket_id, operator_id,
            )
            return json.dumps(result, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_inventory_check(arguments: dict) -> str:
    """库存盘点"""
    async with async_session() as db:
        inventory_id = arguments.get("inventory_id")
        search = arguments.get("search")
        category = arguments.get("category")
        low_stock_only = arguments.get("low_stock_only", False)
        page = int(arguments.get("page", 1))
        page_size = int(arguments.get("page_size", 20))

        if inventory_id:
            inv = await get_inventory(db, uuid.UUID(inventory_id))
            if inv:
                return json.dumps({
                    "id": str(inv.id),
                    "name": inv.name,
                    "category": inv.category,
                    "model_spec": inv.model_spec,
                    "unit": inv.unit,
                    "quantity": inv.quantity,
                    "available_quantity": inv.available_quantity,
                    "min_threshold": inv.min_threshold,
                    "max_threshold": inv.max_threshold,
                    "unit_price": inv.unit_price,
                    "location_id": str(inv.location_id) if inv.location_id else None,
                    "last_restock_at": inv.last_restock_at.isoformat() if inv.last_restock_at else None,
                }, ensure_ascii=False)
            return json.dumps({"error": "库存物品不存在"}, ensure_ascii=False)

        inventories, total = await get_inventories(
            db, page=page, page_size=page_size,
            search=search, category=category, low_stock_only=low_stock_only,
        )
        return json.dumps({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": str(i.id),
                    "name": i.name,
                    "category": i.category,
                    "model_spec": i.model_spec,
                    "unit": i.unit,
                    "quantity": i.quantity,
                    "available_quantity": i.available_quantity,
                    "min_threshold": i.min_threshold,
                    "location_id": str(i.location_id) if i.location_id else None,
                }
                for i in inventories
            ],
        }, ensure_ascii=False)


async def handle_device_status_change(arguments: dict) -> str:
    """设备状态变更"""
    device_id = uuid.UUID(arguments["device_id"])
    action = arguments["action"]
    operator_id = uuid.UUID(arguments.get("operator_id", "00000000-0000-0000-0000-000000000000"))
    comment = arguments.get("comment")
    repair_vendor = arguments.get("repair_vendor")
    repair_cost = arguments.get("repair_cost")
    related_ticket_id = arguments.get("related_ticket_id")

    async with async_session() as db:
        try:
            device = await change_device_status(
                db, device_id, action, operator_id,
                related_ticket_id=uuid.UUID(related_ticket_id) if related_ticket_id else None,
                repair_vendor=repair_vendor,
                repair_cost=repair_cost,
                comment=comment,
            )
            return json.dumps({
                "success": True,
                "device_id": str(device.id),
                "device_no": device.device_no,
                "name": device.name,
                "new_status": device.status,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_transfer_device(arguments: dict) -> str:
    """设备调拨"""
    device_id = uuid.UUID(arguments["device_id"])
    to_location_id = uuid.UUID(arguments["to_location_id"])
    operator_id = uuid.UUID(arguments.get("operator_id", "00000000-0000-0000-0000-000000000000"))
    comment = arguments.get("comment")

    async with async_session() as db:
        try:
            device = await transfer_device(db, device_id, to_location_id, operator_id, comment=comment)
            return json.dumps({
                "success": True,
                "device_id": str(device.id),
                "device_no": device.device_no,
                "name": device.name,
                "new_location_id": str(device.location_id),
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_create_device(arguments: dict) -> str:
    """创建设备"""
    async with async_session() as db:
        try:
            device = await create_device(db, arguments)
            return json.dumps({
                "success": True,
                "device_id": str(device.id),
                "device_no": device.device_no,
                "name": device.name,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_create_inventory(arguments: dict) -> str:
    """创建库存物品"""
    async with async_session() as db:
        try:
            inv = await create_inventory(db, arguments)
            return json.dumps({
                "success": True,
                "inventory_id": str(inv.id),
                "name": inv.name,
                "quantity": inv.quantity,
            }, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_get_locations(arguments: dict) -> str:
    """获取库房位置列表"""
    async with async_session() as db:
        locations = await get_locations(db)
        return json.dumps({
            "total": len(locations),
            "items": [
                {
                    "id": str(loc.id),
                    "name": loc.name,
                    "code": loc.code,
                    "address": loc.address,
                    "status": loc.status,
                    "description": loc.description,
                }
                for loc in locations
            ],
        }, ensure_ascii=False)


async def handle_create_location(arguments: dict) -> str:
    """创建库房位置"""
    async with async_session() as db:
        try:
            loc = await create_location(db, arguments)
            return json.dumps({"success": True, "location_id": str(loc.id), "name": loc.name}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_update_location(arguments: dict) -> str:
    """更新库房位置"""
    location_id = uuid.UUID(arguments.pop("location_id"))
    async with async_session() as db:
        try:
            loc = await update_location(db, location_id, arguments)
            return json.dumps({"success": True, "location_id": str(loc.id), "name": loc.name}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_delete_location(arguments: dict) -> str:
    """删除库房位置"""
    location_id = uuid.UUID(arguments["location_id"])
    async with async_session() as db:
        try:
            await delete_location(db, location_id)
            return json.dumps({"success": True}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_warehouse_overview(arguments: dict) -> str:
    """库房概览统计"""
    async with async_session() as db:
        overview = await get_warehouse_overview(db)
        return json.dumps(overview, ensure_ascii=False)


async def handle_device_logs(arguments: dict) -> str:
    """设备操作日志"""
    device_id = uuid.UUID(arguments["device_id"])
    async with async_session() as db:
        logs = await get_device_logs(db, device_id)
        return json.dumps({
            "device_id": str(device_id),
            "total": len(logs),
            "items": [
                {
                    "id": str(log.id),
                    "action": log.action,
                    "from_status": log.from_status,
                    "to_status": log.to_status,
                    "operator_id": log.operator_id,
                    "comment": log.comment,
                    "created_at": log.created_at.isoformat() if log.created_at else None,
                }
                for log in logs
            ],
        }, ensure_ascii=False)


async def handle_inventory_transactions(arguments: dict) -> str:
    """库存交易记录"""
    inventory_id = uuid.UUID(arguments["inventory_id"])
    page = int(arguments.get("page", 1))
    page_size = int(arguments.get("page_size", 50))
    async with async_session() as db:
        items, total = await get_inventory_transactions(db, inventory_id, page, page_size)
        return json.dumps({
            "inventory_id": str(inventory_id),
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": str(tx.id),
                    "transaction_type": tx.transaction_type,
                    "quantity": tx.quantity,
                    "operator_id": tx.operator_id,
                    "comment": tx.comment,
                    "created_at": tx.created_at.isoformat() if tx.created_at else None,
                }
                for tx in items
            ],
        }, ensure_ascii=False)


async def handle_spare_requests(arguments: dict) -> str:
    """备件申请列表"""
    status = arguments.get("status")
    ticket_id = arguments.get("ticket_id")
    page = int(arguments.get("page", 1))
    page_size = int(arguments.get("page_size", 20))
    async with async_session() as db:
        items, total = await get_spare_requests(db, page, page_size, status, ticket_id)
        return json.dumps({
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [
                {
                    "id": str(req.id),
                    "item_name": req.item_name,
                    "quantity": req.quantity,
                    "ticket_id": req.ticket_id,
                    "status": req.status,
                    "created_at": req.created_at.isoformat() if req.created_at else None,
                    "updated_at": req.updated_at.isoformat() if req.updated_at else None,
                }
                for req in items
            ],
        }, ensure_ascii=False)


async def handle_approve_spare(arguments: dict) -> str:
    """批准备件申请"""
    request_id = uuid.UUID(arguments["request_id"])
    operator_id = uuid.UUID(arguments.get("operator_id", "00000000-0000-0000-0000-000000000000"))
    async with async_session() as db:
        try:
            req = await approve_spare_request(db, request_id, operator_id)
            return json.dumps({"success": True, "request_id": str(req.id), "status": req.status}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_reject_spare(arguments: dict) -> str:
    """拒绝备件申请"""
    request_id = uuid.UUID(arguments["request_id"])
    operator_id = uuid.UUID(arguments.get("operator_id", "00000000-0000-0000-0000-000000000000"))
    reason = arguments.get("reason", "")
    async with async_session() as db:
        try:
            req = await reject_spare_request(db, request_id, operator_id, reason)
            return json.dumps({"success": True, "request_id": str(req.id), "status": req.status}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_fulfill_spare(arguments: dict) -> str:
    """完成备件申请"""
    request_id = uuid.UUID(arguments["request_id"])
    operator_id = uuid.UUID(arguments.get("operator_id", "00000000-0000-0000-0000-000000000000"))
    async with async_session() as db:
        try:
            req = await fulfill_spare_request(db, request_id, operator_id)
            return json.dumps({"success": True, "request_id": str(req.id), "status": req.status}, ensure_ascii=False)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)}, ensure_ascii=False)


async def handle_chat_reply(arguments: dict) -> str:
    """统一对话入口：处理库房相关的自然语言查询"""
    message = arguments.get("message", "") or arguments.get("query", "")
    user_info = arguments.get("user_info", {})

    if not message:
        return json.dumps({"reply": "您好，我是库房管理助手。您可以查询库存、设备、出入库记录等。请问有什么可以帮您？", "data": {}}, ensure_ascii=False)

    # 1. 关键词意图识别（快速，不阻塞）
    intent = "unknown"
    slots = {}
    if any(kw in message for kw in ["库存", "耗材", "备件", "物料", "物品", "存货"]):
        intent = "check_stock"
    elif any(kw in message for kw in ["设备", "机器", "硬件"]):
        intent = "check_device"
    elif any(kw in message for kw in ["统计", "概览", "汇总", "总览"]):
        intent = "query_stats"
    elif any(kw in message for kw in ["入库", "进货", "收货"]):
        intent = "stock_in"
    elif any(kw in message for kw in ["出库", "领用", "领取"]):
        intent = "stock_out"
    elif any(kw in message for kw in ["调拨", "转移"]):
        intent = "transfer"
    elif any(kw in message for kw in ["报废", "废弃"]):
        intent = "scrap"
    elif any(kw in message for kw in ["送修", "维修", "修理"]):
        intent = "send_repair"

    # 2. 根据意图执行操作
    if intent == "check_stock":
        # 查询库存
        # 检测是否是分类查询（如"耗材"→ consumable）
        category_map = {"耗材": "consumable", "备件": "consumable", "物料": "consumable", "网络": "network", "硬件": "hardware", "外设": "peripheral"}
        search = slots.get("item_name", "") or ""
        category = None
        if not search:
            search = message
        # 检查搜索词是否匹配分类关键词
        for kw, cat in category_map.items():
            if kw in search:
                category = cat
                break
        check_args = {"search": search if not category else "", "page": 1, "page_size": 50}
        if category:
            check_args["category"] = category
            check_args["search"] = ""  # 按分类查询时清空搜索词
        result_json = await handle_inventory_check(check_args)
        result = json.loads(result_json)

        if result.get("error"):
            return json.dumps({"reply": f"查询库存时出错：{result['error']}", "data": result}, ensure_ascii=False)

        items = result.get("items", [])
        total = result.get("total", 0)

        if total == 0:
            reply = f"未找到与「{search}」相关的库存物品。请检查物品名称或尝试其他关键词。"
            return json.dumps({"reply": reply, "data": result}, ensure_ascii=False)

        # 构建库存摘要数据
        items_summary = []
        for item in items:
            items_summary.append({
                "name": item.get("name", ""),
                "category": item.get("category", ""),
                "model_spec": item.get("model_spec", ""),
                "unit": item.get("unit", ""),
                "quantity": item.get("quantity", 0),
                "available_quantity": item.get("available_quantity", 0),
                "min_threshold": item.get("min_threshold", 0),
                "location_id": item.get("location_id", ""),
            })

        # 使用简单格式化快速返回（避免 LLM 阻塞导致超时）
        lines = [f"查询到 {total} 条库存记录："]
        for item in items_summary:
            low_stock = " ⚠低库存" if item["quantity"] <= item["min_threshold"] else ""
            lines.append(f"- {item['name']}（{item.get('category', '')}）：库存 {item['quantity']}{item['unit']}，可用 {item['available_quantity']}{item['unit']}{low_stock}")
        reply = "\n".join(lines)

        return json.dumps({"reply": reply, "data": result}, ensure_ascii=False)

    elif intent == "check_device":
        # 查询设备
        device_args = {}
        if slots.get("serial_number"):
            device_args["serial_number"] = slots["serial_number"]
        elif slots.get("device_no"):
            device_args["device_no"] = slots["device_no"]
        else:
            device_args["search"] = slots.get("device_name", message)
        result_json = await handle_device_query(device_args)
        result = json.loads(result_json)

        if result.get("error"):
            return json.dumps({"reply": f"查询设备时出错：{result['error']}", "data": result}, ensure_ascii=False)

        # 单设备查询
        if "device_no" in result:
            device = result
            reply = f"设备信息：\n- 编码：{device.get('device_no', 'N/A')}\n- 名称：{device.get('name', 'N/A')}\n- 型号：{device.get('model', 'N/A')}\n- 状态：{device.get('status', 'N/A')}\n- 序列号：{device.get('serial_number', 'N/A')}"
            return json.dumps({"reply": reply, "data": result}, ensure_ascii=False)

        # 多设备列表
        items = result.get("items", [])
        total = result.get("total", 0)
        if total == 0:
            return json.dumps({"reply": f"未找到相关设备。", "data": result}, ensure_ascii=False)
        lines = [f"查询到 {total} 台设备："]
        for d in items[:20]:
            lines.append(f"- [{d.get('device_no', 'N/A')}] {d.get('name', 'N/A')}（{d.get('status', 'N/A')}）")
        return json.dumps({"reply": "\n".join(lines), "data": result}, ensure_ascii=False)

    elif intent == "query_stats":
        # 库房概览统计
        result_json = await handle_warehouse_overview({})
        result = json.loads(result_json)
        reply = f"库房概览：\n- 总设备数：{result.get('total_devices', 0)}\n- 库存物品种类：{result.get('total_inventory_items', 0)}\n- 库房位置数：{result.get('total_locations', 0)}"
        return json.dumps({"reply": reply, "data": result}, ensure_ascii=False)

    elif intent in ("stock_in", "stock_out", "device_in", "device_out", "transfer", "scrap", "send_repair"):
        # 操作类意图，需要更多信息确认
        intent_names = {
            "stock_in": "入库", "stock_out": "出库",
            "device_in": "设备录入", "device_out": "设备出库",
            "transfer": "调拨", "scrap": "报废", "send_repair": "送修"
        }
        name = intent_names.get(intent, intent)
        return json.dumps({"reply": f"您想要执行「{name}」操作。请提供详细信息，例如物品名称、数量、库房位置等。", "data": {"intent": intent, "slots": slots}}, ensure_ascii=False)

    else:
        # 未识别意图，返回功能引导
        reply = "您好，我是库房管理助手。您可以：\n1. 查询库存 - 如「查询打印纸库存」\n2. 查询设备 - 如「查询设备xxx」\n3. 查看库房概览 - 如「库房统计」\n4. 出入库操作\n5. 设备调拨/报废/送修"

        return json.dumps({"reply": reply, "data": {}}, ensure_ascii=False)


# ---- MCP Tool Definitions ----

MCP_TOOLS = [
    {
        "name": "chat_reply",
        "description": "统一对话入口：处理库房相关的自然语言查询，支持库存查询、设备查询、库房概览、出入库操作等",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string", "description": "用户消息"},
                "query": {"type": "string", "description": "用户查询（与 message 二选一）"},
                "session_id": {"type": "string", "description": "会话ID"},
                "history": {"type": "array", "description": "对话历史"},
                "user_info": {"type": "object", "description": "用户信息"},
            },
            "required": [],
        },
    },
    {
        "name": "stock_in",
        "description": "库存入库：将指定数量的物品入库到库存中",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inventory_id": {"type": "string", "description": "库存物品ID (UUID)"},
                "quantity": {"type": "integer", "description": "入库数量"},
                "operator_id": {"type": "string", "description": "操作人ID"},
                "unit_price": {"type": "number", "description": "单价"},
                "comment": {"type": "string", "description": "备注"},
            },
            "required": ["inventory_id", "quantity"],
        },
    },
    {
        "name": "stock_out",
        "description": "库存出库：从库存中扣减指定数量的物品",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inventory_id": {"type": "string", "description": "库存物品ID (UUID)"},
                "quantity": {"type": "integer", "description": "出库数量"},
                "operator_id": {"type": "string", "description": "操作人ID"},
                "related_ticket_id": {"type": "string", "description": "关联工单ID"},
                "comment": {"type": "string", "description": "备注"},
            },
            "required": ["inventory_id", "quantity"],
        },
    },
    {
        "name": "device_query",
        "description": "设备查询：查询设备信息，支持按ID、序列号、设备编码、状态筛选",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备ID (UUID)"},
                "serial_number": {"type": "string", "description": "设备序列号"},
                "device_no": {"type": "string", "description": "设备编码"},
                "status": {"type": "string", "description": "设备状态"},
                "search": {"type": "string", "description": "搜索关键词"},
                "page": {"type": "integer", "description": "页码"},
                "page_size": {"type": "integer", "description": "每页数量"},
            },
        },
    },
    {
        "name": "ocr_recognize",
        "description": "OCR铭牌识别：识别设备铭牌图片，提取序列号、型号、品牌等信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "image_base64": {"type": "string", "description": "Base64编码的图片数据"},
            },
            "required": ["image_base64"],
        },
    },
    {
        "name": "spare_request",
        "description": "备件申请：创建备件申请记录，用于从Dispatch Agent接收备件需求",
        "inputSchema": {
            "type": "object",
            "properties": {
                "item_name": {"type": "string", "description": "备件名称"},
                "quantity": {"type": "integer", "description": "申请数量"},
                "ticket_id": {"type": "string", "description": "关联工单ID"},
                "operator_id": {"type": "string", "description": "操作人ID"},
            },
            "required": ["item_name", "quantity", "ticket_id"],
        },
    },
    {
        "name": "inventory_check",
        "description": "库存盘点：查询库存信息，支持按ID、搜索词、低库存筛选",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inventory_id": {"type": "string", "description": "库存物品ID (UUID)"},
                "search": {"type": "string", "description": "搜索关键词"},
                "low_stock_only": {"type": "boolean", "description": "仅显示低库存"},
                "page": {"type": "integer", "description": "页码"},
                "page_size": {"type": "integer", "description": "每页数量"},
            },
        },
    },
    {
        "name": "device_status_change",
        "description": "设备状态变更：变更设备生命周期状态（如送修、报废、调拨等）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备ID (UUID)"},
                "action": {"type": "string", "description": "操作类型: allocate/scrap/deliver/cancel_allocate/return_damaged/send_repair/repair_done/restock"},
                "operator_id": {"type": "string", "description": "操作人ID"},
                "comment": {"type": "string", "description": "备注"},
                "repair_vendor": {"type": "string", "description": "维修商（送修时使用）"},
                "repair_cost": {"type": "number", "description": "维修费用"},
                "related_ticket_id": {"type": "string", "description": "关联工单ID"},
            },
            "required": ["device_id", "action"],
        },
    },
    {
        "name": "transfer_device",
        "description": "设备调拨：将设备从一个库房调拨到另一个库房",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备ID (UUID)"},
                "to_location_id": {"type": "string", "description": "目标库房ID (UUID)"},
                "operator_id": {"type": "string", "description": "操作人ID"},
                "comment": {"type": "string", "description": "备注"},
            },
            "required": ["device_id", "to_location_id"],
        },
    },
    {
        "name": "create_device",
        "description": "创建设备：在库房中创建新的设备记录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "serial_number": {"type": "string", "description": "设备序列号"},
                "name": {"type": "string", "description": "设备名称"},
                "model": {"type": "string", "description": "设备型号"},
                "category": {"type": "string", "description": "设备类别"},
                "brand": {"type": "string", "description": "品牌"},
                "location_id": {"type": "string", "description": "库房位置ID"},
                "purchase_price": {"type": "number", "description": "采购价格"},
                "supplier": {"type": "string", "description": "供应商"},
                "notes": {"type": "string", "description": "备注"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "create_inventory",
        "description": "创建库存物品：在库房中创建新的库存物品记录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "物品名称"},
                "category": {"type": "string", "description": "物品类别"},
                "model_spec": {"type": "string", "description": "型号规格"},
                "unit": {"type": "string", "description": "单位"},
                "quantity": {"type": "integer", "description": "初始数量"},
                "min_threshold": {"type": "integer", "description": "最低库存阈值"},
                "max_threshold": {"type": "integer", "description": "最高库存阈值"},
                "unit_price": {"type": "number", "description": "单价"},
                "location_id": {"type": "string", "description": "库房位置ID"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "get_locations",
        "description": "获取库房位置列表：查询所有库房位置",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "create_location",
        "description": "创建库房位置：创建新的库房/库位",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "位置名称"},
                "code": {"type": "string", "description": "位置编码"},
                "address": {"type": "string", "description": "地址"},
                "status": {"type": "string", "description": "状态"},
                "description": {"type": "string", "description": "描述"},
            },
            "required": ["name"],
        },
    },
    {
        "name": "update_location",
        "description": "更新库房位置：修改库房位置信息",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "位置ID (UUID)"},
                "name": {"type": "string", "description": "位置名称"},
                "address": {"type": "string", "description": "地址"},
                "status": {"type": "string", "description": "状态"},
                "description": {"type": "string", "description": "描述"},
            },
            "required": ["location_id"],
        },
    },
    {
        "name": "delete_location",
        "description": "删除库房位置：删除指定的库房位置",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location_id": {"type": "string", "description": "位置ID (UUID)"},
            },
            "required": ["location_id"],
        },
    },
    {
        "name": "warehouse_overview",
        "description": "库房概览统计：获取库房整体统计数据",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "device_logs",
        "description": "设备操作日志：查询指定设备的操作日志",
        "inputSchema": {
            "type": "object",
            "properties": {
                "device_id": {"type": "string", "description": "设备ID (UUID)"},
            },
            "required": ["device_id"],
        },
    },
    {
        "name": "inventory_transactions",
        "description": "库存交易记录：查询指定库存物品的交易记录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "inventory_id": {"type": "string", "description": "库存物品ID (UUID)"},
                "page": {"type": "integer", "description": "页码"},
                "page_size": {"type": "integer", "description": "每页数量"},
            },
            "required": ["inventory_id"],
        },
    },
    {
        "name": "spare_requests",
        "description": "备件申请列表：查询备件申请记录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "申请状态"},
                "ticket_id": {"type": "string", "description": "关联工单ID"},
                "page": {"type": "integer", "description": "页码"},
                "page_size": {"type": "integer", "description": "每页数量"},
            },
        },
    },
    {
        "name": "approve_spare",
        "description": "批准备件申请：批准备件申请记录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "申请ID (UUID)"},
                "operator_id": {"type": "string", "description": "操作人ID"},
            },
            "required": ["request_id"],
        },
    },
    {
        "name": "reject_spare",
        "description": "拒绝备件申请：拒绝备件申请记录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "申请ID (UUID)"},
                "reason": {"type": "string", "description": "拒绝原因"},
                "operator_id": {"type": "string", "description": "操作人ID"},
            },
            "required": ["request_id"],
        },
    },
    {
        "name": "fulfill_spare",
        "description": "完成备件申请：完成备件申请并扣减库存",
        "inputSchema": {
            "type": "object",
            "properties": {
                "request_id": {"type": "string", "description": "申请ID (UUID)"},
                "operator_id": {"type": "string", "description": "操作人ID"},
            },
            "required": ["request_id"],
        },
    },
]

# ---- MCP Resource Definitions ----

MCP_RESOURCES = [
    {
        "uri": "device://{device_id}",
        "name": "Device Details",
        "description": "设备详细信息",
        "mimeType": "application/json",
    },
    {
        "uri": "inventory://{item_id}",
        "name": "Inventory Item Details",
        "description": "库存物品详细信息",
        "mimeType": "application/json",
    },
    {
        "uri": "location://{location_id}",
        "name": "Warehouse Location Details",
        "description": "库房位置详细信息",
        "mimeType": "application/json",
    },
]

# ---- Tool Handler Dispatch ----

TOOL_HANDLERS = {
    "chat_reply": handle_chat_reply,
    "stock_in": handle_stock_in,
    "stock_out": handle_stock_out,
    "device_query": handle_device_query,
    "ocr_recognize": handle_ocr_recognize,
    "spare_request": handle_spare_request,
    "inventory_check": handle_inventory_check,
    "device_status_change": handle_device_status_change,
    "transfer_device": handle_transfer_device,
    "create_device": handle_create_device,
    "create_inventory": handle_create_inventory,
    "get_locations": handle_get_locations,
    "create_location": handle_create_location,
    "update_location": handle_update_location,
    "delete_location": handle_delete_location,
    "warehouse_overview": handle_warehouse_overview,
    "device_logs": handle_device_logs,
    "inventory_transactions": handle_inventory_transactions,
    "spare_requests": handle_spare_requests,
    "approve_spare": handle_approve_spare,
    "reject_spare": handle_reject_spare,
    "fulfill_spare": handle_fulfill_spare,
}


async def handle_resource_read(uri: str) -> str:
    """处理 MCP 资源读取"""
    async with async_session() as db:
        if uri.startswith("device://"):
            device_id = uri.replace("device://", "")
            device = await get_device(db, uuid.UUID(device_id))
            if device:
                return json.dumps({
                    "id": str(device.id),
                    "device_no": device.device_no,
                    "serial_number": device.serial_number,
                    "name": device.name,
                    "model": device.model,
                    "category": device.category,
                    "brand": device.brand,
                    "status": device.status,
                    "location_id": str(device.location_id) if device.location_id else None,
                    "purchase_date": str(device.purchase_date) if device.purchase_date else None,
                    "warranty_expiry": str(device.warranty_expiry) if device.warranty_expiry else None,
                    "purchase_price": device.purchase_price,
                    "supplier": device.supplier,
                    "notes": device.notes,
                    "created_at": device.created_at.isoformat(),
                    "updated_at": device.updated_at.isoformat(),
                }, ensure_ascii=False)
            return json.dumps({"error": "Device not found"}, ensure_ascii=False)

        elif uri.startswith("inventory://"):
            item_id = uri.replace("inventory://", "")
            inv = await get_inventory(db, uuid.UUID(item_id))
            if inv:
                return json.dumps({
                    "id": str(inv.id),
                    "name": inv.name,
                    "category": inv.category,
                    "model_spec": inv.model_spec,
                    "unit": inv.unit,
                    "quantity": inv.quantity,
                    "available_quantity": inv.available_quantity,
                    "min_threshold": inv.min_threshold,
                    "max_threshold": inv.max_threshold,
                    "unit_price": inv.unit_price,
                    "location_id": str(inv.location_id) if inv.location_id else None,
                    "last_restock_at": inv.last_restock_at.isoformat() if inv.last_restock_at else None,
                }, ensure_ascii=False)
            return json.dumps({"error": "Inventory item not found"}, ensure_ascii=False)

        elif uri.startswith("location://"):
            location_id = uri.replace("location://", "")
            result = await db.execute(
                select(WarehouseLocation).where(WarehouseLocation.id == uuid.UUID(location_id))
            )
            loc = result.scalar_one_or_none()
            if loc:
                return json.dumps({
                    "id": str(loc.id),
                    "name": loc.name,
                    "code": loc.code,
                    "address": loc.address,
                    "status": loc.status,
                    "description": loc.description,
                }, ensure_ascii=False)
            return json.dumps({"error": "Location not found"}, ensure_ascii=False)

        return json.dumps({"error": "Unknown resource URI"}, ensure_ascii=False)


def get_mcp_tools() -> list:
    """获取 MCP 工具定义列表"""
    return MCP_TOOLS


def get_mcp_resources() -> list:
    """获取 MCP 资源定义列表"""
    return MCP_RESOURCES


async def call_tool(tool_name: str, arguments: dict) -> str:
    """调用 MCP 工具"""
    handler = TOOL_HANDLERS.get(tool_name)
    if handler:
        return await handler(arguments)
    return json.dumps({"error": f"Unknown tool: {tool_name}"}, ensure_ascii=False)