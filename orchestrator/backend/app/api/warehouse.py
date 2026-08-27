"""Warehouse API 代理 - 将请求转发到 Warehouse Agent，含 JWT 角色权限校验和模拟降级"""
from fastapi import APIRouter, Request, HTTPException, Depends
from app.core.mcp_client import mcp_client
from app.core.tracer import generate_trace_id
from app.api.deps import (
    require_storekeeper,
    require_admin,
    require_role,
    require_any_authenticated,
)
from app.config import settings
import datetime as dt
import json
import logging

logger = logging.getLogger("warehouse")

router = APIRouter(prefix="/api/v1/warehouse")

# ==================== 模拟数据 ====================

now = dt.datetime.utcnow().isoformat() + "Z"

_MOCK_DEVICES = [
    {"id": "DEV-001", "name": "HP LaserJet Pro M404dn", "category": "printer", "brand": "HP", "model": "M404dn", "serial_number": "SN-HP-001", "status": "in_stock", "location": "A-01", "created_at": now, "updated_at": now},
    {"id": "DEV-002", "name": "Dell U2723QE 显示器", "category": "display", "brand": "Dell", "model": "U2723QE", "serial_number": "SN-DELL-002", "status": "in_use", "location": "17F-03", "assigned_to": "张三", "created_at": now, "updated_at": now},
    {"id": "DEV-003", "name": "ThinkPad X1 Carbon", "category": "laptop", "brand": "Lenovo", "model": "X1C-Gen11", "serial_number": "SN-LEN-003", "status": "in_repair", "location": "维修中心", "created_at": now, "updated_at": now},
    {"id": "DEV-004", "name": "Cisco Catalyst 2960", "category": "network", "brand": "Cisco", "model": "WS-C2960X-24TS-L", "serial_number": "SN-CISCO-004", "status": "allocated", "location": "B-03", "created_at": now, "updated_at": now},
    {"id": "DEV-005", "name": "HP ProDesk 600 G6", "category": "desktop", "brand": "HP", "model": "ProDesk 600", "serial_number": "SN-HP-005", "status": "scrapped", "location": "报废区", "scrapped_reason": "主板损坏无法修复", "created_at": now, "updated_at": now},
]

_MOCK_INVENTORY = [
    {"id": "INV-001", "name": "HP 12A 墨盒", "category": "consumable", "quantity": 50, "min_threshold": 10, "unit": "个", "location": "A-01", "created_at": now, "updated_at": now},
    {"id": "INV-002", "name": "打印机定影膜", "category": "consumable", "quantity": 2, "min_threshold": 10, "unit": "个", "location": "A-02", "created_at": now, "updated_at": now},
    {"id": "INV-003", "name": "网线 CAT6 3米", "category": "network", "quantity": 200, "min_threshold": 30, "unit": "根", "location": "B-01", "created_at": now, "updated_at": now},
    {"id": "INV-004", "name": "DP 转 HDMI 转接头", "category": "accessory", "quantity": 8, "min_threshold": 15, "unit": "个", "location": "B-02", "created_at": now, "updated_at": now},
    {"id": "INV-005", "name": "SSD 固态硬盘 512GB", "category": "hardware", "quantity": 25, "min_threshold": 5, "unit": "块", "location": "C-01", "created_at": now, "updated_at": now},
    {"id": "INV-006", "name": "DDR4 内存 16GB", "category": "hardware", "quantity": 40, "min_threshold": 10, "unit": "条", "location": "C-02", "created_at": now, "updated_at": now},
]

_MOCK_SPARE_REQUESTS = [
    {"id": "SPR-001", "item_name": "HP 12A 墨盒", "quantity": 3, "ticket_id": "TKT-001", "requested_by": "张三", "status": "pending", "created_at": now, "updated_at": now},
    {"id": "SPR-002", "item_name": "SSD 固态硬盘 512GB", "quantity": 1, "ticket_id": "TKT-002", "requested_by": "李四", "status": "approved", "created_at": now, "updated_at": now},
]

_MOCK_LOCATIONS = [
    {"id": "LOC-001", "name": "A-01", "description": "耗材区-打印机", "type": "shelf"},
    {"id": "LOC-002", "name": "A-02", "description": "耗材区-配件", "type": "shelf"},
    {"id": "LOC-003", "name": "B-01", "description": "网络设备区", "type": "cabinet"},
    {"id": "LOC-004", "name": "B-02", "description": "配件区", "type": "shelf"},
    {"id": "LOC-005", "name": "C-01", "description": "硬件区-存储", "type": "cabinet"},
    {"id": "LOC-006", "name": "C-02", "description": "硬件区-内存", "type": "cabinet"},
    {"id": "LOC-007", "name": "维修中心", "description": "待维修设备存放区", "type": "room"},
    {"id": "LOC-008", "name": "报废区", "description": "报废设备存放区", "type": "room"},
]

_MOCK_ALERTS = [
    {"id": "ALT-001", "type": "low_stock", "item_name": "打印机定影膜", "current_qty": 2, "threshold": 10, "severity": "warning", "created_at": now},
    {"id": "ALT-002", "type": "low_stock", "item_name": "DP 转 HDMI 转接头", "current_qty": 8, "threshold": 15, "severity": "warning", "created_at": now},
    {"id": "ALT-003", "type": "idle_device", "device_name": "HP ProDesk 600 G6", "device_id": "DEV-005", "idle_days": 90, "severity": "info", "created_at": now},
]

_MOCK_STATS = {
    "total_devices": 5,
    "total_inventory_types": 6,
    "total_inventory_items": 325,
    "low_stock_count": 2,
    "pending_spare_requests": 1,
    "devices_in_repair": 1,
    "idle_devices": 1,
    "total_spare_requests": 12,
    "approved_spare_requests": 8,
    "by_device_status": {"in_stock": 1, "in_use": 1, "in_repair": 1, "allocated": 1, "scrapped": 1},
    "by_category": {"printer": 1, "display": 1, "laptop": 1, "network": 1, "desktop": 1},
}

_MOCK_TRANSACTIONS = [
    {"id": "TXN-001", "inventory_id": "INV-001", "type": "stock_in", "quantity": 50, "operator": "storekeeper", "created_at": now},
    {"id": "TXN-002", "inventory_id": "INV-002", "type": "stock_in", "quantity": 10, "operator": "storekeeper", "created_at": now},
    {"id": "TXN-003", "inventory_id": "INV-002", "type": "stock_out", "quantity": 8, "operator": "storekeeper", "ticket_id": "TKT-001", "created_at": now},
]

_MOCK_DEVICE_LOGS = [
    {"id": "LOG-001", "device_id": "DEV-001", "action": "create", "operator": "storekeeper", "comment": "新设备入库", "created_at": now},
    {"id": "LOG-002", "device_id": "DEV-002", "action": "allocate", "operator": "storekeeper", "comment": "分配给张三", "created_at": now},
    {"id": "LOG-003", "device_id": "DEV-002", "action": "deliver", "operator": "storekeeper", "comment": "交付使用", "created_at": now},
    {"id": "LOG-004", "device_id": "DEV-003", "action": "send_repair", "operator": "storekeeper", "comment": "送修", "created_at": now},
]

_COUNTERS = {"device": 6, "inventory": 7, "spare": 3, "location": 9, "alert": 4, "transaction": 4, "device_log": 5}


def _warehouse_mock_response(action: str, params: dict) -> dict:
    """根据 action 返回模拟数据，不依赖 LLM"""
    now_ts = dt.datetime.utcnow().isoformat() + "Z"

    # ==================== 设备管理 ====================
    if action == "device_query":
        device_id = params.get("device_id")
        if device_id:
            for d in _MOCK_DEVICES:
                if d["id"] == device_id:
                    return d
            return {"error": "Device not found"}

        status = params.get("status")
        search = (params.get("search") or "").lower()
        devices = _MOCK_DEVICES
        if status:
            devices = [d for d in devices if d["status"] == status]
        if search:
            devices = [d for d in devices if search in d["name"].lower() or search in (d.get("serial_number") or "").lower()]
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 20))
        return {"items": devices, "total": len(devices)}

    elif action == "create_device":
        dev_id = f"DEV-{_COUNTERS['device']:03d}"
        _COUNTERS["device"] += 1
        new_device = {
            "id": dev_id,
            "name": params.get("name", "新设备"),
            "category": params.get("category", "other"),
            "brand": params.get("brand", ""),
            "model": params.get("model", ""),
            "serial_number": params.get("serial_number", f"SN-{dev_id}"),
            "status": "in_stock",
            "location": params.get("location", "A-01"),
            "created_at": now_ts,
            "updated_at": now_ts,
        }
        _MOCK_DEVICES.append(new_device)
        # 记录操作日志
        _MOCK_DEVICE_LOGS.append({
            "id": f"LOG-{_COUNTERS['device_log']:03d}",
            "device_id": dev_id,
            "action": "create",
            "operator": params.get("operator", "storekeeper"),
            "comment": "新设备入库",
            "created_at": now_ts,
        })
        _COUNTERS["device_log"] += 1
        return new_device

    elif action == "device_status_change":
        device_id = params.get("device_id", "")
        new_action = params.get("action", "")
        comment = params.get("comment", "")
        status_map = {
            "allocate": "allocated",
            "deliver": "in_use",
            "return_damaged": "damaged",
            "send_repair": "in_repair",
            "repair_done": "repaired",
            "restock": "in_stock",
            "scrap": "scrapped",
        }
        new_status = status_map.get(new_action, new_action)
        for d in _MOCK_DEVICES:
            if d["id"] == device_id:
                d["status"] = new_status
                d["updated_at"] = now_ts
                # 记录操作日志
                _MOCK_DEVICE_LOGS.append({
                    "id": f"LOG-{_COUNTERS['device_log']:03d}",
                    "device_id": device_id,
                    "action": new_action,
                    "operator": params.get("operator", "storekeeper"),
                    "comment": comment,
                    "created_at": now_ts,
                })
                _COUNTERS["device_log"] += 1
                return d
        return {"error": "Device not found", "device_id": device_id}

    elif action == "transfer_device":
        device_id = params.get("device_id", "")
        new_location = params.get("new_location", params.get("location", ""))
        for d in _MOCK_DEVICES:
            if d["id"] == device_id:
                d["location"] = new_location
                d["updated_at"] = now_ts
                return d
        return {"error": "Device not found"}

    elif action == "device_logs":
        device_id = params.get("device_id", "")
        logs = [log for log in _MOCK_DEVICE_LOGS if log["device_id"] == device_id]
        return {"items": logs, "total": len(logs)}

    # ==================== 库存管理 ====================
    elif action == "inventory_check":
        inv_id = params.get("inventory_id")
        if inv_id:
            for item in _MOCK_INVENTORY:
                if item["id"] == inv_id:
                    return item
            return {"error": "Inventory item not found"}

        search = (params.get("search") or "").lower()
        low_stock_only = params.get("low_stock_only", False)
        items = _MOCK_INVENTORY
        if search:
            items = [i for i in items if search in i["name"].lower()]
        if low_stock_only:
            items = [i for i in items if i["quantity"] <= i["min_threshold"]]
        page = int(params.get("page", 1))
        page_size = int(params.get("page_size", 20))
        return {"items": items, "total": len(items)}

    elif action == "create_inventory":
        inv_id = f"INV-{_COUNTERS['inventory']:03d}"
        _COUNTERS["inventory"] += 1
        new_item = {
            "id": inv_id,
            "name": params.get("name", "新物品"),
            "category": params.get("category", "other"),
            "quantity": int(params.get("quantity", 0)),
            "min_threshold": int(params.get("min_threshold", 10)),
            "unit": params.get("unit", "个"),
            "location": params.get("location", "A-01"),
            "created_at": now_ts,
            "updated_at": now_ts,
        }
        _MOCK_INVENTORY.append(new_item)
        # 记录入库交易
        _MOCK_TRANSACTIONS.append({
            "id": f"TXN-{_COUNTERS['transaction']:03d}",
            "inventory_id": inv_id,
            "type": "stock_in",
            "quantity": new_item["quantity"],
            "operator": params.get("operator", "storekeeper"),
            "created_at": now_ts,
        })
        _COUNTERS["transaction"] += 1
        return new_item

    elif action == "stock_in":
        inv_id = params.get("inventory_id", "")
        qty = int(params.get("quantity", 0))
        for item in _MOCK_INVENTORY:
            if item["id"] == inv_id:
                item["quantity"] += qty
                item["updated_at"] = now_ts
                _MOCK_TRANSACTIONS.append({
                    "id": f"TXN-{_COUNTERS['transaction']:03d}",
                    "inventory_id": inv_id,
                    "type": "stock_in",
                    "quantity": qty,
                    "operator": params.get("operator", "storekeeper"),
                    "created_at": now_ts,
                })
                _COUNTERS["transaction"] += 1
                return item
        return {"error": "Inventory item not found"}

    elif action == "stock_out":
        inv_id = params.get("inventory_id", "")
        qty = int(params.get("quantity", 0))
        for item in _MOCK_INVENTORY:
            if item["id"] == inv_id:
                if item["quantity"] < qty:
                    return {"error": "Insufficient stock", "current": item["quantity"], "requested": qty}
                item["quantity"] -= qty
                item["updated_at"] = now_ts
                _MOCK_TRANSACTIONS.append({
                    "id": f"TXN-{_COUNTERS['transaction']:03d}",
                    "inventory_id": inv_id,
                    "type": "stock_out",
                    "quantity": qty,
                    "operator": params.get("operator", "storekeeper"),
                    "ticket_id": params.get("ticket_id", ""),
                    "created_at": now_ts,
                })
                _COUNTERS["transaction"] += 1
                return item
        return {"error": "Inventory item not found"}

    elif action == "inventory_transactions":
        inv_id = params.get("inventory_id", "")
        txns = [t for t in _MOCK_TRANSACTIONS if t["inventory_id"] == inv_id]
        return {"items": txns, "total": len(txns)}

    # ==================== 备件申请 ====================
    elif action == "spare_requests":
        return {"items": _MOCK_SPARE_REQUESTS, "total": len(_MOCK_SPARE_REQUESTS)}

    elif action == "create_spare_request":
        spr_id = f"SPR-{_COUNTERS['spare']:03d}"
        _COUNTERS["spare"] += 1
        new_spr = {
            "id": spr_id,
            "item_name": params.get("item_name", ""),
            "quantity": int(params.get("quantity", 1)),
            "ticket_id": params.get("ticket_id", ""),
            "requested_by": params.get("requested_by", ""),
            "status": "pending",
            "created_at": now_ts,
            "updated_at": now_ts,
        }
        _MOCK_SPARE_REQUESTS.append(new_spr)
        return new_spr

    elif action == "approve_spare":
        request_id = params.get("request_id", "")
        for s in _MOCK_SPARE_REQUESTS:
            if s["id"] == request_id:
                s["status"] = "approved"
                s["updated_at"] = now_ts
                return s
        return {"error": "Spare request not found"}

    elif action == "reject_spare":
        request_id = params.get("request_id", "")
        reason = params.get("reason", "")
        for s in _MOCK_SPARE_REQUESTS:
            if s["id"] == request_id:
                s["status"] = "rejected"
                s["updated_at"] = now_ts
                return s
        return {"error": "Spare request not found"}

    elif action == "fulfill_spare":
        request_id = params.get("request_id", "")
        for s in _MOCK_SPARE_REQUESTS:
            if s["id"] == request_id:
                s["status"] = "fulfilled"
                s["updated_at"] = now_ts
                return s
        return {"error": "Spare request not found"}

    # ==================== 库房位置 ====================
    elif action == "get_locations":
        return {"items": _MOCK_LOCATIONS, "total": len(_MOCK_LOCATIONS)}

    elif action == "create_location":
        loc_id = f"LOC-{_COUNTERS['location']:03d}"
        _COUNTERS["location"] += 1
        new_loc = {
            "id": loc_id,
            "name": params.get("name", "新位置"),
            "description": params.get("description", ""),
            "type": params.get("type", "shelf"),
        }
        _MOCK_LOCATIONS.append(new_loc)
        return new_loc

    elif action == "update_location":
        location_id = params.get("location_id", "")
        for loc in _MOCK_LOCATIONS:
            if loc["id"] == location_id:
                loc["name"] = params.get("name", loc["name"])
                loc["description"] = params.get("description", loc["description"])
                loc["type"] = params.get("type", loc["type"])
                return loc
        return {"error": "Location not found"}

    elif action == "delete_location":
        location_id = params.get("location_id", "")
        for i, loc in enumerate(_MOCK_LOCATIONS):
            if loc["id"] == location_id:
                _MOCK_LOCATIONS.pop(i)
                return {"status": "deleted", "location_id": location_id}
        return {"error": "Location not found"}

    # ==================== 统计和告警 ====================
    elif action == "warehouse_overview":
        return _MOCK_STATS

    elif action == "get_alerts":
        return {"alerts": _MOCK_ALERTS, "total": len(_MOCK_ALERTS)}

    return {"error": f"Unknown action: {action}"}


async def _call_warehouse(action: str, params: dict, trace_id: str) -> dict:
    """调用 Warehouse Agent，失败时降级到模拟数据"""
    result = await mcp_client.call_tool("warehouse-agent", action, params, trace_id)
    if result.get("degraded"):
        logger.info(f"Warehouse mock fallback: action={action}")
        return _warehouse_mock_response(action, params)
    return result


# ==================== 设备管理 ====================

@router.get("/devices")
async def get_devices(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    params = dict(request.query_params)
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("device_query", {
        "status": params.get("status"),
        "search": params.get("search"),
        "page": int(params.get("page", 1)),
        "page_size": int(params.get("page_size", 20)),
    }, trace_id)


@router.get("/devices/{device_id}")
async def get_device(device_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("device_query", {"device_id": device_id}, trace_id)


@router.post("/devices")
async def create_device(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    body["operator"] = user["username"]
    return await _call_warehouse("create_device", body, trace_id)


@router.put("/devices/{device_id}/status")
async def device_status_change(device_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    body["operator"] = user["username"]
    return await _call_warehouse("device_status_change", {"device_id": device_id, **body}, trace_id)


@router.put("/devices/{device_id}/transfer")
async def transfer_device(device_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("transfer_device", {"device_id": device_id, **body}, trace_id)


@router.get("/devices/{device_id}/logs")
async def get_device_logs(device_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("device_logs", {"device_id": device_id}, trace_id)


# ==================== 库存管理 ====================

@router.get("/inventory")
async def get_inventory(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    params = dict(request.query_params)
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("inventory_check", {
        "search": params.get("search"),
        "low_stock_only": params.get("low_stock_only") == "true",
        "page": int(params.get("page", 1)),
        "page_size": int(params.get("page_size", 20)),
    }, trace_id)


@router.get("/inventory/{item_id}")
async def get_inventory_item(item_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("inventory_check", {"inventory_id": item_id}, trace_id)


@router.post("/inventory")
async def create_inventory(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    body["operator"] = user["username"]
    return await _call_warehouse("create_inventory", body, trace_id)


@router.post("/inventory/{item_id}/stock-in")
async def stock_in(item_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    body["operator"] = user["username"]
    return await _call_warehouse("stock_in", {"inventory_id": item_id, **body}, trace_id)


@router.post("/inventory/{item_id}/stock-out")
async def stock_out(item_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    body["operator"] = user["username"]
    return await _call_warehouse("stock_out", {"inventory_id": item_id, **body}, trace_id)


@router.get("/inventory/{item_id}/transactions")
async def get_inventory_transactions(item_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("inventory_transactions", {"inventory_id": item_id}, trace_id)


# ==================== 备件申请 ====================

@router.get("/spare-requests")
async def get_spare_requests(request: Request, user: dict = Depends(require_role("storekeeper", "admin", "engineer"))):
    params = dict(request.query_params)
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("spare_requests", params, trace_id)


@router.post("/spare-requests")
async def create_spare_request(request: Request, user: dict = Depends(require_role("storekeeper", "admin", "engineer"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    body["requested_by"] = body.get("requested_by") or user["username"]
    return await _call_warehouse("create_spare_request", body, trace_id)


@router.put("/spare-requests/{request_id}/approve")
async def approve_spare_request(request_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("approve_spare", {"request_id": request_id}, trace_id)


@router.put("/spare-requests/{request_id}/reject")
async def reject_spare_request(request_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    params = dict(request.query_params)
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("reject_spare", {"request_id": request_id, "reason": params.get("reason", "")}, trace_id)


@router.put("/spare-requests/{request_id}/fulfill")
async def fulfill_spare_request(request_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("fulfill_spare", {"request_id": request_id}, trace_id)


# ==================== 库房位置 ====================

@router.get("/locations")
async def get_locations(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("get_locations", {}, trace_id)


@router.post("/locations")
async def create_location(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("create_location", body, trace_id)


@router.put("/locations/{location_id}")
async def update_location(location_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("update_location", {"location_id": location_id, **body}, trace_id)


@router.delete("/locations/{location_id}")
async def delete_location(location_id: str, request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("delete_location", {"location_id": location_id}, trace_id)


# ==================== 统计和告警 ====================

@router.get("/stats/overview")
async def get_warehouse_stats(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("warehouse_overview", {}, trace_id)


@router.get("/alerts")
async def get_alerts(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_warehouse("get_alerts", {}, trace_id)


# ==================== OCR ====================

@router.post("/ocr/recognize")
async def ocr_recognize(request: Request, user: dict = Depends(require_role("storekeeper", "admin"))):
    return {"success": False, "error": "OCR 功能需要直接调用 Warehouse Agent"}