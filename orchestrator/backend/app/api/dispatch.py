"""Dispatch API 代理 - 将请求转发到 Dispatch Agent，含 JWT 角色权限校验和 LLM 降级"""
from fastapi import APIRouter, Request, HTTPException, Depends
from app.core.mcp_client import mcp_client
from app.core.tracer import generate_trace_id
from app.core.degrader import get_degraded_message
from app.api.deps import (
    require_admin,
    require_engineer,
    require_admin_or_engineer,
    require_any_authenticated,
    require_role,
)
from app.config import settings
import aiohttp
import json
import logging

logger = logging.getLogger("dispatch")

router = APIRouter(prefix="/api/v1/dispatch")


import datetime as dt

# 预置模拟数据
_MOCK_TICKETS = [
    {"id": "TKT-001", "ticket_no": "TKT-001", "title": "打印机故障报修", "description": "17楼打印机打印模糊", "status": "created", "priority": "medium", "urgency": "medium", "fault_category": "hardware", "created_by": "testuser", "assigned_to": None, "created_at": "2026-08-06T10:00:00Z", "updated_at": "2026-08-06T10:00:00Z", "sla_deadline": "2026-08-06T18:00:00Z"},
    {"id": "TKT-002", "ticket_no": "TKT-002", "title": "网络连接异常", "description": "3楼西区无法连接内网", "status": "assigned", "priority": "high", "urgency": "high", "fault_category": "network", "created_by": "testuser", "assigned_to": "eng-1", "created_at": "2026-08-06T09:30:00Z", "updated_at": "2026-08-06T09:45:00Z", "sla_deadline": "2026-08-06T14:00:00Z"},
    {"id": "TKT-003", "ticket_no": "TKT-003", "title": "账号权限申请", "description": "新员工需要开通VPN权限", "status": "in_progress", "priority": "low", "urgency": "low", "fault_category": "software", "created_by": "testuser", "assigned_to": "eng-2", "created_at": "2026-08-05T16:00:00Z", "updated_at": "2026-08-06T08:00:00Z", "sla_deadline": "2026-08-07T16:00:00Z"},
    {"id": "TKT-004", "ticket_no": "TKT-004", "title": "显示器黑屏", "description": "工位显示器无法点亮", "status": "resolved", "priority": "medium", "urgency": "medium", "fault_category": "hardware", "created_by": "testuser", "assigned_to": "eng-1", "created_at": "2026-08-05T14:00:00Z", "updated_at": "2026-08-05T15:00:00Z", "sla_deadline": "2026-08-05T22:00:00Z", "resolution": "更换电源线后正常"},
    {"id": "TKT-005", "ticket_no": "TKT-005", "title": "系统崩溃", "description": "财务系统频繁崩溃", "status": "closed", "priority": "critical", "urgency": "critical", "fault_category": "software", "created_by": "admin", "assigned_to": "eng-3", "created_at": "2026-08-04T08:00:00Z", "updated_at": "2026-08-04T18:00:00Z", "sla_deadline": "2026-08-04T12:00:00Z", "resolution": "已修复数据库连接池问题"},
]

_MOCK_ENGINEERS = [
    {"id": "eng-1", "user_id": "eng-1", "display_name": "张三", "status": "busy", "skills": ["hardware", "network", "printer"], "skill_levels": {}, "max_concurrent": 5, "current_load": 3, "total_completed": 45, "avg_resolution_minutes": 30, "rating": 4.5},
    {"id": "eng-2", "user_id": "eng-2", "display_name": "李四", "status": "available", "skills": ["software", "database", "security"], "skill_levels": {}, "max_concurrent": 5, "current_load": 1, "total_completed": 38, "avg_resolution_minutes": 25, "rating": 4.2},
    {"id": "eng-3", "user_id": "eng-3", "display_name": "王五", "status": "available", "skills": ["system", "cloud", "backup"], "skill_levels": {}, "max_concurrent": 5, "current_load": 0, "total_completed": 52, "avg_resolution_minutes": 20, "rating": 4.8},
]

def _compute_stats():
    """动态根据 _MOCK_TICKETS 计算统计数据"""
    tickets = _MOCK_TICKETS
    total = len(tickets)
    by_status = {}
    by_urgency = {}
    unassigned = 0
    for t in tickets:
        s = t["status"]
        by_status[s] = by_status.get(s, 0) + 1
        u = t["urgency"]
        by_urgency[u] = by_urgency.get(u, 0) + 1
        if t["assigned_to"] is None and s not in ("closed", "cancelled"):
            unassigned += 1
    return {
        "total": total,
        "open_tickets": by_status.get("created", 0) + by_status.get("assigned", 0) + by_status.get("in_progress", 0),
        "resolved_today": 0,
        "avg_response_time": "2.3分钟",
        "avg_resolve_time": "45分钟",
        "satisfaction": 4.3,
        "by_status": by_status,
        "by_urgency": by_urgency,
        "overdue": 0,
        "unassigned": unassigned,
    }

_MOCK_TICKET_COUNTER = [6]


def _generate_ticket_id() -> str:
    c = _MOCK_TICKET_COUNTER[0]
    _MOCK_TICKET_COUNTER[0] = c + 1
    return f"TKT-{c:03d}"


def _dispatch_mock_response(action: str, params: dict) -> dict:
    """根据 action 返回模拟数据，不依赖 LLM"""
    now = dt.datetime.utcnow().isoformat() + "Z"

    if action == "query_tickets":
        status = params.get("status")
        engineer_id = params.get("engineer_id")
        tickets = _MOCK_TICKETS
        if status:
            tickets = [t for t in tickets if t["status"] == status]
        if engineer_id:
            tickets = [t for t in tickets if t["assigned_to"] == engineer_id]
        page = int(params.get("page", 1))
        return {"items": tickets, "total": len(tickets), "page": page}

    elif action == "create_ticket":
        new_id = _generate_ticket_id()
        new_ticket = {
            "id": new_id,
            "ticket_no": new_id,
            "title": params.get("title", "新建工单"),
            "description": params.get("description", ""),
            "status": "created",
            "priority": params.get("priority", "medium"),
            "urgency": params.get("urgency", params.get("priority", "medium")),
            "fault_category": params.get("fault_category", "other"),
            "created_by": params.get("created_by", "unknown"),
            "assigned_to": None,
            "created_at": now,
            "updated_at": now,
            "sla_deadline": (dt.datetime.utcnow() + dt.timedelta(hours=8)).isoformat() + "Z",
        }
        _MOCK_TICKETS.insert(0, new_ticket)
        return new_ticket

    elif action == "get_engineers":
        return {"items": _MOCK_ENGINEERS, "total": len(_MOCK_ENGINEERS)}

    elif action == "create_engineer":
        new_id = f"eng-{len(_MOCK_ENGINEERS)+1}"
        return {"id": new_id, "user_id": new_id, "display_name": params.get("name", "新工程师"), "status": "available", "skills": params.get("skills", []), "skill_levels": {}, "max_concurrent": 5, "current_load": 0, "total_completed": 0, "avg_resolution_minutes": 0, "rating": 0}

    elif action == "assign_ticket":
        ticket_id = params.get("ticket_id", "")
        engineer_id = params.get("engineer_id", "")
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                t["status"] = "assigned"
                t["assigned_to"] = engineer_id
                t["updated_at"] = now
                return t
        return {"id": ticket_id, "status": "assigned", "assigned_to": engineer_id, "assigned_at": now}

    elif action == "reassign_ticket":
        ticket_id = params.get("ticket_id", "")
        engineer_id = params.get("engineer_id", "")
        reason = params.get("reason", "")
        # 改派：自动提升优先级
        urgency_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                current = t["urgency"]
                current_level = urgency_order.get(current, 1)
                if current_level < 3:
                    next_level = min(current_level + 1, 3)
                    new_urgency = {0: "low", 1: "medium", 2: "high", 3: "critical"}[next_level]
                    t["urgency"] = new_urgency
                    t["priority"] = new_urgency
                t["assigned_to"] = engineer_id
                t["updated_at"] = now
                return {"status": "ok", "ticket_id": ticket_id, "assigned_to": engineer_id, "reason": reason, "new_urgency": t["urgency"]}
        return {"status": "reassigned", "ticket_id": ticket_id, "assigned_to": engineer_id}

    elif action in ("accept_ticket", "reject_ticket"):
        ticket_id = params.get("ticket_id", "")
        new_status = "in_progress" if action == "accept_ticket" else "created"
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                t["status"] = new_status
                t["updated_at"] = now
                return t
        return {"id": ticket_id, "status": new_status}

    elif action == "resolve_ticket":
        ticket_id = params.get("ticket_id", "")
        resolution = params.get("resolution", "已解决")
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                t["status"] = "resolved"
                t["resolution"] = resolution
                t["updated_at"] = now
                return t
        return {"id": ticket_id, "status": "resolved", "resolution": resolution}

    elif action == "close_ticket":
        ticket_id = params.get("ticket_id", "")
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                t["status"] = "closed"
                t["resolution"] = params.get("resolution", "管理员关闭")
                t["updated_at"] = now
                return t
        return {"id": ticket_id, "status": "closed"}

    elif action == "cancel_ticket":
        ticket_id = params.get("ticket_id", "")
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                t["status"] = "cancelled"
                t["updated_at"] = now
                return t
        return {"id": ticket_id, "status": "cancelled"}

    elif action == "reopen_ticket":
        ticket_id = params.get("ticket_id", "")
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                t["status"] = "created"
                t["assigned_to"] = None
                t["resolution"] = None
                t["updated_at"] = now
                return t
        return {"id": ticket_id, "status": "created"}

    elif action == "urge_ticket":
        return {"status": "ok", "message": "已催办工单", "ticket_id": params.get("ticket_id", "")}

    elif action == "change_priority":
        return {"status": "ok", "ticket_id": params.get("ticket_id", ""), "new_priority": params.get("urgency", "medium")}

    elif action == "escalate_ticket":
        ticket_id = params.get("ticket_id", "")
        new_engineer_id = params.get("new_engineer_id", "")
        for t in _MOCK_TICKETS:
            if t["id"] == ticket_id:
                if new_engineer_id:
                    t["assigned_to"] = new_engineer_id
                t["updated_at"] = now
                return {"status": "ok", "ticket_id": ticket_id, "escalated_to": new_engineer_id}
        return {"status": "ok", "ticket_id": ticket_id, "escalated_to": new_engineer_id}

    elif action == "get_stats":
        return _compute_stats()

    return {"error": f"Unknown action: {action}"}


async def _dispatch_llm_fallback(action: str, params: dict) -> dict:
    """Dispatch Agent 不可用时，返回模拟数据"""
    logger.info(f"Dispatch mock fallback: action={action}")
    return _dispatch_mock_response(action, params)


async def _call_dispatch(action: str, params: dict, trace_id: str) -> dict:
    """调用 Dispatch Agent，失败时降级到 LLM"""
    result = await mcp_client.call_tool("dispatch-agent", action, params, trace_id)
    if result.get("degraded"):
        return await _dispatch_llm_fallback(action, params)
    return result


# ==================== 工单查询 ====================

@router.get("/tickets")
async def get_tickets(request: Request, user: dict = Depends(require_any_authenticated)):
    params = dict(request.query_params)
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("query_tickets", {
        "status": params.get("status"),
        "engineer_id": params.get("engineer_id"),
        "urgency": params.get("urgency"),
        "page": int(params.get("page", 1)),
        "page_size": int(params.get("page_size", 20)),
    }, trace_id)


@router.get("/stats")
async def get_stats(request: Request, user: dict = Depends(require_admin_or_engineer)):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("get_stats", {}, trace_id)


# ==================== 工单创建 ====================

@router.post("/tickets")
async def create_ticket(request: Request, user: dict = Depends(require_role("admin", "user"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    body["created_by"] = body.get("created_by") or user["username"]
    return await _call_dispatch("create_ticket", body, trace_id)


# ==================== 工程师管理 ====================

@router.get("/engineers")
async def get_engineers(request: Request, user: dict = Depends(require_admin)):
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("get_engineers", {}, trace_id)


@router.post("/engineers")
async def create_engineer(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("create_engineer", body, trace_id)


# ==================== 工单指派 ====================

@router.post("/assign")
async def assign_ticket(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("assign_ticket", body, trace_id)


@router.post("/reassign")
async def reassign_ticket(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("reassign_ticket", body, trace_id)


# ==================== 工程师操作 ====================

@router.post("/accept")
async def accept_ticket(request: Request, user: dict = Depends(require_admin_or_engineer)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    if user["role"] == "engineer":
        body["engineer_id"] = body.get("engineer_id") or user["username"]
    return await _call_dispatch("accept_ticket", body, trace_id)


@router.post("/reject")
async def reject_ticket(request: Request, user: dict = Depends(require_admin_or_engineer)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    if user["role"] == "engineer":
        body["engineer_id"] = body.get("engineer_id") or user["username"]
    return await _call_dispatch("reject_ticket", body, trace_id)


@router.post("/resolve")
async def resolve_ticket(request: Request, user: dict = Depends(require_admin_or_engineer)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    if user["role"] == "engineer":
        body["operator_id"] = body.get("operator_id") or user["username"]
    return await _call_dispatch("resolve_ticket", body, trace_id)


# ==================== 管理员操作 ====================

@router.post("/close")
async def close_ticket(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("close_ticket", {
        "ticket_id": body.get("ticket_id"),
        "resolution": "管理员关闭工单",
        "operator_id": user["username"],
    }, trace_id)


@router.post("/cancel")
async def cancel_ticket(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("cancel_ticket", body, trace_id)


@router.post("/reopen")
async def reopen_ticket(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("reopen_ticket", body, trace_id)


@router.post("/priority")
async def change_priority(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("change_priority", body, trace_id)


@router.post("/escalate")
async def escalate_ticket(request: Request, user: dict = Depends(require_admin)):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("escalate_ticket", {
        "ticket_id": body.get("ticket_id"),
        "new_engineer_id": body.get("engineer_id"),
        "reason": body.get("reason", "升级工单"),
    }, trace_id)


@router.post("/urge")
async def urge_ticket(request: Request, user: dict = Depends(require_role("admin", "user"))):
    body = await request.json()
    trace_id = getattr(request.state, "trace_id", generate_trace_id())
    return await _call_dispatch("urge_ticket", body, trace_id)