"""MCP Server for Dispatch Agent - Ticket dispatch and lifecycle management."""
import json
import os
import re
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional

from mcp.server.fastmcp import FastMCP
from sqlalchemy import select, func
from app.database import async_session
from app.models.ticket import Ticket
from app.models.ticket_log import TicketLog
from app.models.engineer import EngineerProfile
from app.models.urge_record import UrgeRecord
from app.core.ticket_state_machine import (
    validate_transition,
    get_next_status,
    calculate_sla_deadline,
)
from app.core.dispatch_engine import find_best_engineer
from app.core.notification import notification_service
from app.config import settings

logger = logging.getLogger(__name__)

mcp = FastMCP("dispatch-agent")


# ==================== 报修信息补全相关 ====================

LOCATION_PROMPT = "好的，为了尽快安排工程师上门，请告诉我设备所在的位置（例如：几号楼、几层、哪个房间）。"
CONTACT_PROMPT = "请提供您的联系方式（手机号或分机号），方便工程师到达后与您联系。"

# 工单编号格式，如 WO-20260827-9316
TICKET_NO_RE = re.compile(r"WO-\d{8}-\d+", re.IGNORECASE)


def _last_assistant_reply(history) -> str:
    """返回对话历史中最后一条 assistant 回复内容。"""
    for h in reversed(history or []):
        if isinstance(h, dict) and h.get("role") == "assistant":
            return h.get("content", "")
    return ""


def _find_location_answer(history) -> str:
    """从历史中提取用户回答的「位置」（位置提问之后的用户消息）。"""
    msgs = [h for h in (history or []) if isinstance(h, dict)]
    for i, h in enumerate(msgs):
        if h.get("role") == "assistant" and LOCATION_PROMPT in h.get("content", ""):
            for nxt in msgs[i + 1:]:
                if nxt.get("role") == "user":
                    return nxt.get("content", "").strip()
            break
    return ""


def _build_created_reply(result: dict, fault_category: str, urgency: str,
                         location: str, contact: str, display_name: str, created_by: str) -> dict:
    """构建工单创建成功的回复文本。"""
    if not result.get("success"):
        return {"reply": f"工单创建失败：{result.get('error', '未知错误')}", "data": result}

    lines = [
        "工单已创建成功！",
        f"工单编号：{result['ticket_no']}",
        f"状态：{result.get('status', 'created')}",
        f"故障类型：{fault_category}",
        f"紧急程度：{urgency}",
    ]
    if location:
        lines.append(f"位置：{location}")
    if contact:
        lines.append(f"联系方式：{contact}")
    if display_name and created_by:
        lines.append(f"需求人：{display_name}（{created_by}）")
    elif created_by:
        lines.append(f"需求人：{created_by}")
    lines.append("")
    lines.append("工程师将尽快上门处理，请保持联系电话畅通。您可以输入工单编号查询进度。")
    return {"reply": "\n".join(lines), "data": result}


def _format_ticket_detail(t: dict) -> str:
    """构建单个工单查询结果的回复文本。"""
    lines = [
        f"工单编号：{t['ticket_no']}",
        f"标题：{t.get('title', '')}",
        f"状态：{t.get('status', 'created')}",
        f"故障类型：{t.get('fault_category', 'other')}",
        f"紧急程度：{t.get('urgency', 'medium')}",
    ]
    if t.get("location"):
        lines.append(f"位置：{t['location']}")
    if t.get("contact"):
        lines.append(f"联系方式：{t['contact']}")
    return "\n".join(lines)


def _to_uuid(s: str) -> uuid.UUID:
    """Convert string to UUID, safely."""
    if isinstance(s, uuid.UUID):
        return s
    return uuid.UUID(s)


def register_mcp_tools():
    """Register all MCP tools and resources."""

    # ==================== Tools ====================

    @mcp.tool()
    async def chat_reply(message: str = "", query: str = "", session_id: str = "", history: list = None, user_info: dict = None, **kwargs) -> dict:
        """统一对话入口：根据用户意图执行工单操作并返回回复"""
        user_msg = message or query
        user_info = user_info or {}
        created_by = user_info.get("username", "")
        display_name = user_info.get("display_name", "")

        # 从对话历史中提取上下文信息（仅从用户消息中提取，避免 assistant 回复污染）
        context_title = ""
        context_desc = ""
        if history:
            # 第一轮：查找包含报修/故障关键词的用户消息
            for h in history:
                if h.get("role") not in ("user",):
                    continue
                content = h.get("content", "")
                if any(kw in content for kw in ["报修", "打印机", "打印", "故障", "坏了", "连接不上", "连不上", "打不开", "没反应", "不能用", "出问题", "不工作"]):
                    context_title = content[:100]
                    context_desc = content
            # 第二轮：如果没找到关键词，取最近一条有实质内容的用户消息（排除当前消息和短确认）
            if not context_title:
                for h in reversed(history):
                    if h.get("role") not in ("user",):
                        continue
                    content = h.get("content", "")
                    if content == user_msg:
                        continue
                    if len(content) <= 5:
                        continue
                    context_title = content[:100]
                    context_desc = content
                    break

        # 判断意图：拒绝（先检查，避免被确认关键词误匹配）
        rejection_keywords = ["不需要", "不用", "不要", "不了", "不必", "算了", "不用了", "先不"]
        if any(kw in user_msg for kw in rejection_keywords):
            return {"reply": "好的，如有需要请随时联系我。", "data": {}}

        # ============ 多轮信息补全：位置 + 联系方式 ============
        last_assistant = _last_assistant_reply(history)
        awaiting_location = LOCATION_PROMPT in last_assistant
        awaiting_contact = CONTACT_PROMPT in last_assistant

        # 上一轮在追问位置，本轮用户回答位置 → 继续追问联系方式
        if awaiting_location:
            location = user_msg.strip()
            return {"reply": CONTACT_PROMPT, "data": {"pending_location": location}}

        # 上一轮在追问联系方式，本轮用户回答联系方式 → 信息齐全，创建工单
        if awaiting_contact:
            location = _find_location_answer(history)
            contact = user_msg.strip()
            title = context_title or user_msg
            description = context_desc or user_msg
            fault_category = "printer" if any(kw in (title + description) for kw in ["打印", "打印机"]) else "other"
            urgency = "medium"
            result = await create_ticket(
                title=title,
                description=description,
                fault_category=fault_category,
                urgency=urgency,
                location=location,
                contact=contact,
                created_by=created_by,
            )
            return _build_created_reply(result, fault_category, urgency, location, contact, display_name, created_by)

        # 判断意图：显式要求创建工单（"报修/生成工单/创建工单/提交工单"或要求工程师上门）→ 先补全位置/联系方式
        direct_ticket_keywords = ["报修", "生成工单", "创建工单", "提交工单",
                                  "需要工程师", "工程师上门", "需要人", "派人来", "派人", "上门"]
        # 症状类描述（故障、坏了等）→ 先反问确认，避免误建工单
        symptom_keywords = ["帮我", "帮忙", "故障", "坏了", "不能用", "出问题", "不工作"]
        if any(kw in user_msg for kw in direct_ticket_keywords):
            # 位置缺失，先询问位置
            return {"reply": LOCATION_PROMPT, "data": {}}

        if any(kw in user_msg for kw in symptom_keywords):
            return {"reply": "需要我为您生成报修工单吗？", "data": {}}

        # 判断意图：用户确认创建工单（仅当消息较短时，避免"需要多久"等问句误匹配）
        confirm_keywords = ["需要", "是", "好的", "可以", "确认", "行", "嗯", "对", "创建吧", "生成吧", "提交吧"]
        # 过滤问句：包含疑问词的不视为确认
        question_words = ["多久", "什么", "多少", "怎么", "吗", "？", "?", "在哪", "谁", "何时", "为什么"]
        is_question = any(p in user_msg for p in question_words)
        # 消息长度 ≤ 5 字符才视为确认，避免长问句误匹配
        if any(kw in user_msg for kw in confirm_keywords) and len(user_msg) <= 5 and not is_question:
            if not context_title:
                return {"reply": "抱歉，我没有找到之前的报修信息。请重新描述您的问题，我会为您创建工单。", "data": {}}
            # 确认后先补全位置
            return {"reply": LOCATION_PROMPT, "data": {}}

        # 判断意图：查询指定工单编号（如 WO-20260827-9316）
        ticket_no_match = TICKET_NO_RE.search(user_msg)
        if ticket_no_match:
            ticket_no = ticket_no_match.group(0)
            result = await query_tickets(ticket_no=ticket_no, created_by=created_by, page=1, page_size=10)
            items = result.get("items", [])
            if items:
                t = items[0]
                detail = _format_ticket_detail(t)
                return {"reply": detail, "data": result}
            return {"reply": f"未找到工单编号为 {ticket_no} 的工单，请核对编号是否正确。", "data": result}

        # 判断意图：查询工单
        if any(kw in user_msg for kw in ["查询", "进度", "状态", "我的工单", "工单列表"]):
            result = await query_tickets(created_by=created_by, page=1, page_size=10)
            items = result.get("items", [])
            if items:
                lines = [f"共 {result['total']} 个工单："]
                for t in items[:5]:
                    lines.append(f"- {t['ticket_no']}: {t['title']} [{t['status']}]")
                return {"reply": "\n".join(lines), "data": result}
            return {"reply": "当前没有工单记录。", "data": result}

        # 判断意图：催单
        if "催" in user_msg and "工单" in user_msg:
            return {"reply": "请提供需要催办的工单编号，格式如：WO-20240814-0001"}

        # 默认回复
        return {"reply": "您好，我是工单调度助手。您可以通过以下方式使用：\n\n1. 报修设备故障 - 直接描述问题，我会帮您生成工单\n2. 查询工单 - 输入「查询工单」或「我的工单」\n3. 催办工单 - 输入工单编号和「催单」", "data": {}}

    @mcp.tool()
    async def create_ticket(
        title: str,
        description: str = "",
        fault_category: str = "other",
        urgency: str = "medium",
        location: Optional[str] = None,
        contact: Optional[str] = None,
        device_info: Optional[dict] = None,
        created_by: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Create a new dispatch ticket."""
        async with async_session() as db:
            ticket = Ticket(
                ticket_no=_generate_ticket_no(),
                title=title,
                description=description,
                fault_category=fault_category,
                urgency=urgency,
                location=location,
                contact=contact,
                device_info=device_info,
                created_by=created_by,
                sla_deadline=calculate_sla_deadline(urgency),
            )
            db.add(ticket)
            await db.commit()
            await db.refresh(ticket)

            return {
                "success": True,
                "ticket_id": str(ticket.id),
                "ticket_no": ticket.ticket_no,
                "status": ticket.status,
                "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
            }

    @mcp.tool()
    async def assign_ticket(
        ticket_id: str,
        engineer_id: Optional[str] = None,
        operator_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Assign a ticket to an engineer."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            if not validate_transition(ticket.status, "assign"):
                return {"success": False, "error": f"Cannot assign ticket in status '{ticket.status}'"}

            if not engineer_id:
                best = await find_best_engineer(ticket)
                if not best:
                    return {"success": False, "error": "No available engineer found"}
                engineer_id = best.user_id

            old_status = ticket.status
            ticket.status = get_next_status(ticket.status, "assign")
            ticket.assigned_to = engineer_id
            ticket.assigned_at = datetime.now(timezone.utc)

            log = TicketLog(
                ticket_id=ticket.id,
                action="assign",
                operator_id=operator_id,
                from_status=old_status,
                to_status=ticket.status,
                comment=f"Assigned to engineer {engineer_id}",
            )
            db.add(log)
            await db.commit()

            await notification_service.notify_new_ticket(engineer_id, {
                "ticket_id": str(ticket.id),
                "ticket_no": ticket.ticket_no,
                "title": ticket.title,
                "urgency": ticket.urgency,
            })

            return {"success": True, "ticket_id": str(ticket.id), "status": ticket.status, "assigned_to": engineer_id}

    @mcp.tool()
    async def query_tickets(
        status: Optional[str] = None,
        engineer_id: Optional[str] = None,
        urgency: Optional[str] = None,
        ticket_no: Optional[str] = None,
        created_by: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Query tickets with filters."""
        async with async_session() as db:
            conditions = []
            if status:
                conditions.append(Ticket.status == status)
            if engineer_id:
                conditions.append(Ticket.assigned_to == engineer_id)
            if urgency:
                conditions.append(Ticket.urgency == urgency)
            if ticket_no:
                conditions.append(Ticket.ticket_no == ticket_no)
            if created_by:
                conditions.append(Ticket.created_by == created_by)

            # Count with simple query
            count_q = select(func.count(Ticket.id))
            for c in conditions:
                count_q = count_q.where(c)
            total = (await db.execute(count_q)).scalar() or 0

            # Main query
            query = select(Ticket)
            for c in conditions:
                query = query.where(c)
            offset = (page - 1) * page_size
            query = query.order_by(Ticket.created_at.desc()).offset(offset).limit(page_size)
            result = await db.execute(query)
            tickets = result.scalars().all()

            items = [
                {
                    "id": str(t.id),
                    "ticket_no": t.ticket_no,
                    "title": t.title,
                    "description": t.description,
                    "fault_category": t.fault_category,
                    "urgency": t.urgency,
                    "status": t.status,
                    "assigned_to": t.assigned_to,
                    "created_by": t.created_by,
                    "location": t.location,
                    "contact": t.contact,
                    "sla_deadline": t.sla_deadline.isoformat() if t.sla_deadline else None,
                    "created_at": t.created_at.isoformat() if t.created_at else None,
                    "updated_at": t.updated_at.isoformat() if t.updated_at else None,
                }
                for t in tickets
            ]

            return {"total": total, "page": page, "page_size": page_size, "items": items}

    @mcp.tool()
    async def get_engineers(
        status: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Get list of engineers."""
        async with async_session() as db:
            query = select(EngineerProfile)
            if status:
                query = query.where(EngineerProfile.status == status)
            result = await db.execute(query)
            engineers = result.scalars().all()

            items = [
                {
                    "id": str(e.id),
                    "user_id": e.user_id,
                    "display_name": e.display_name,
                    "skills": e.skills,
                    "status": e.status,
                    "location": e.location,
                    "current_load": e.current_load,
                    "max_concurrent": e.max_concurrent,
                    "total_completed": e.total_completed,
                    "rating": e.rating,
                }
                for e in engineers
            ]

            return {"total": len(items), "items": items}

    @mcp.tool()
    async def urge_ticket(
        ticket_id: str,
        operator_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Urge/speed up a ticket."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            urge = UrgeRecord(
                ticket_id=ticket.id,
                urge_type="manual",
                urged_by=operator_id,
                message="管理员催促处理工单",
            )
            db.add(urge)

            if ticket.assigned_to:
                await notification_service.notify_urge(ticket.assigned_to, {
                    "ticket_id": str(ticket.id),
                    "ticket_no": ticket.ticket_no,
                    "message": "管理员催促处理工单，请尽快处理",
                })

            await db.commit()
            return {"success": True, "ticket_id": str(ticket.id), "ticket_no": ticket.ticket_no}

    @mcp.tool()
    async def resolve_ticket(
        ticket_id: str,
        resolution: str,
        operator_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Resolve/complete a ticket."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            if not validate_transition(ticket.status, "resolve"):
                return {"success": False, "error": f"Cannot resolve ticket in status '{ticket.status}'"}

            old_status = ticket.status
            ticket.status = get_next_status(ticket.status, "resolve")
            ticket.resolution = resolution
            ticket.resolved_at = datetime.now(timezone.utc)

            log = TicketLog(
                ticket_id=ticket.id,
                action="resolve",
                operator_id=operator_id,
                from_status=old_status,
                to_status=ticket.status,
                comment=resolution,
            )
            db.add(log)
            await db.commit()

            return {"success": True, "ticket_id": str(ticket.id), "status": ticket.status}

    @mcp.tool()
    async def reassign_ticket(
        ticket_id: str,
        new_engineer_id: str,
        reason: Optional[str] = None,
        operator_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Reassign a ticket to a different engineer."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            if not validate_transition(ticket.status, "reassign"):
                return {"success": False, "error": f"Cannot reassign ticket in status '{ticket.status}'"}

            old_engineer = ticket.assigned_to
            old_status = ticket.status
            ticket.status = get_next_status(ticket.status, "reassign")
            ticket.assigned_to = new_engineer_id
            ticket.assigned_at = datetime.now(timezone.utc)

            log = TicketLog(
                ticket_id=ticket.id,
                action="reassign",
                operator_id=operator_id,
                from_status=old_status,
                to_status=ticket.status,
                comment=f"Reassigned from {old_engineer} to {new_engineer_id}. Reason: {reason or 'N/A'}",
            )
            db.add(log)

            await notification_service.notify_new_ticket(new_engineer_id, {
                "ticket_id": str(ticket.id),
                "ticket_no": ticket.ticket_no,
                "title": ticket.title,
                "urgency": ticket.urgency,
                "reassigned": True,
                "previous_engineer": old_engineer,
            })

            await db.commit()
            return {"success": True, "ticket_id": str(ticket.id), "status": ticket.status, "assigned_to": new_engineer_id}

    @mcp.tool()
    async def cancel_ticket(
        ticket_id: str,
        reason: Optional[str] = None,
        operator_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Cancel a ticket."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            if not validate_transition(ticket.status, "cancel"):
                return {"success": False, "error": f"Cannot cancel ticket in status '{ticket.status}'"}

            old_status = ticket.status
            ticket.status = get_next_status(ticket.status, "cancel")

            log = TicketLog(
                ticket_id=ticket.id,
                action="cancel",
                operator_id=operator_id,
                from_status=old_status,
                to_status=ticket.status,
                comment=reason or "Cancelled",
            )
            db.add(log)
            await db.commit()

            return {"success": True, "ticket_id": str(ticket.id), "status": ticket.status}

    @mcp.tool()
    async def create_engineer(
        user_id: str,
        display_name: str,
        skills: Optional[list] = None,
        skill_levels: Optional[dict] = None,
        status: Optional[str] = "available",
        location: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Create a new engineer profile."""
        async with async_session() as db:
            engineer = EngineerProfile(
                user_id=user_id,
                display_name=display_name,
                skills=skills or [],
                skill_levels=skill_levels or {},
                status=status or "available",
                location=location,
            )
            db.add(engineer)
            await db.commit()
            await db.refresh(engineer)
            return {"success": True, "id": str(engineer.id), "user_id": engineer.user_id}

    @mcp.tool()
    async def reopen_ticket(
        ticket_id: str,
        reason: Optional[str] = None,
        operator_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Reopen a closed ticket."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}
            if ticket.status != "closed":
                return {"success": False, "error": "Only closed tickets can be reopened"}

            old_status = ticket.status
            ticket.status = "created"
            ticket.assigned_to = None
            ticket.resolution = None

            log = TicketLog(
                ticket_id=ticket.id,
                action="reopen",
                operator_id=operator_id,
                from_status=old_status,
                to_status=ticket.status,
                comment=reason or "Reopened",
            )
            db.add(log)
            await db.commit()
            return {"success": True, "ticket_id": str(ticket.id), "status": ticket.status}

    @mcp.tool()
    async def change_priority(
        ticket_id: str,
        urgency: str,
        operator_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Change ticket priority/urgency."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            old_urgency = ticket.urgency
            ticket.urgency = urgency
            ticket.sla_deadline = calculate_sla_deadline(urgency)

            log = TicketLog(
                ticket_id=ticket.id,
                action="change_priority",
                operator_id=operator_id,
                comment=f"Priority changed from {old_urgency} to {urgency}",
            )
            db.add(log)
            await db.commit()
            return {"success": True, "ticket_id": str(ticket.id), "urgency": urgency}

    @mcp.tool()
    async def accept_ticket(
        ticket_id: str,
        engineer_id: str = "",
        trace_id: Optional[str] = None,
    ) -> dict:
        """Engineer accepts a ticket."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            if not validate_transition(ticket.status, "accept"):
                return {"success": False, "error": f"Cannot accept ticket in status '{ticket.status}'"}

            if not engineer_id:
                engineer_id = ticket.assigned_to

            old_status = ticket.status
            ticket.status = "in_progress"
            ticket.assigned_to = engineer_id

            log = TicketLog(
                ticket_id=ticket.id,
                action="accept",
                operator_id=engineer_id,
                from_status=old_status,
                to_status=ticket.status,
                comment="Engineer accepted ticket",
            )
            db.add(log)
            await db.commit()
            return {"success": True, "ticket_id": str(ticket.id), "status": ticket.status}

    @mcp.tool()
    async def reject_ticket(
        ticket_id: str,
        reason: Optional[str] = None,
        engineer_id: Optional[str] = None,
        trace_id: Optional[str] = None,
    ) -> dict:
        """Engineer rejects a ticket."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return {"success": False, "error": "Ticket not found"}

            if ticket.status != "assigned":
                return {"success": False, "error": f"Cannot reject ticket in status '{ticket.status}'"}

            old_status = ticket.status
            ticket.status = "created"
            ticket.assigned_to = None

            log = TicketLog(
                ticket_id=ticket.id,
                action="reject",
                operator_id=engineer_id,
                from_status=old_status,
                to_status=ticket.status,
                comment=reason or "Engineer rejected ticket",
            )
            db.add(log)
            await db.commit()
            return {"success": True, "ticket_id": str(ticket.id), "status": ticket.status}

    @mcp.tool()
    async def get_stats(
        trace_id: Optional[str] = None,
    ) -> dict:
        """Get ticket statistics."""
        async with async_session() as db:
            total_result = await db.execute(select(func.count()).select_from(Ticket))
            total = total_result.scalar()

            status_result = await db.execute(
                select(Ticket.status, func.count()).group_by(Ticket.status)
            )
            by_status = {row[0]: row[1] for row in status_result.all()}

            urgency_result = await db.execute(
                select(Ticket.urgency, func.count()).group_by(Ticket.urgency)
            )
            by_urgency = {row[0]: row[1] for row in urgency_result.all()}

            now = datetime.now(timezone.utc)
            overdue_result = await db.execute(
                select(func.count()).where(
                    Ticket.sla_deadline < now,
                    Ticket.status.in_(["created", "assigned", "in_progress"]),
                )
            )
            overdue = overdue_result.scalar()

            unassigned_result = await db.execute(
                select(func.count()).where(Ticket.status == "created")
            )
            unassigned = unassigned_result.scalar()

            return {
                "total": total,
                "by_status": by_status,
                "by_urgency": by_urgency,
                "overdue": overdue,
                "unassigned": unassigned,
            }

    # ==================== Resources ====================

    @mcp.resource("ticket://{ticket_id}")
    async def get_ticket_resource(ticket_id: str) -> str:
        """Get ticket details as a resource."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return json.dumps({"error": "Ticket not found"}, ensure_ascii=False)

            logs_result = await db.execute(
                select(TicketLog).where(TicketLog.ticket_id == ticket_id).order_by(TicketLog.created_at)
            )
            logs = logs_result.scalars().all()

            return json.dumps({
                "id": str(ticket.id),
                "ticket_no": ticket.ticket_no,
                "title": ticket.title,
                "description": ticket.description,
                "fault_category": ticket.fault_category,
                "urgency": ticket.urgency,
                "status": ticket.status,
                "assigned_to": ticket.assigned_to,
                "location": ticket.location,
                "contact": ticket.contact,
                "device_info": ticket.device_info,
                "resolution": ticket.resolution,
                "sla_deadline": ticket.sla_deadline.isoformat() if ticket.sla_deadline else None,
                "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
                "updated_at": ticket.updated_at.isoformat() if ticket.updated_at else None,
                "logs": [
                    {
                        "id": str(log.id),
                        "action": log.action,
                        "from_status": log.from_status,
                        "to_status": log.to_status,
                        "comment": log.comment,
                        "created_at": log.created_at.isoformat() if log.created_at else None,
                    }
                    for log in logs
                ],
            }, ensure_ascii=False)

    @mcp.resource("engineer://{engineer_id}")
    async def get_engineer_resource(engineer_id: str) -> str:
        """Get engineer details as a resource."""
        async with async_session() as db:
            result = await db.execute(
                select(EngineerProfile).where(EngineerProfile.user_id == engineer_id)
            )
            engineer = result.scalar_one_or_none()
            if not engineer:
                return json.dumps({"error": "Engineer not found"}, ensure_ascii=False)

            return json.dumps({
                "id": str(engineer.id),
                "user_id": engineer.user_id,
                "display_name": engineer.display_name,
                "skills": engineer.skills,
                "skill_levels": engineer.skill_levels,
                "status": engineer.status,
                "location": engineer.location,
                "max_concurrent": engineer.max_concurrent,
                "current_load": engineer.current_load,
                "total_completed": engineer.total_completed,
                "rating": engineer.rating,
            }, ensure_ascii=False)

    @mcp.resource("sla://{ticket_id}")
    async def get_sla_resource(ticket_id: str) -> str:
        """Get SLA information for a ticket."""
        async with async_session() as db:
            result = await db.execute(select(Ticket).where(Ticket.id == _to_uuid(ticket_id)))
            ticket = result.scalar_one_or_none()
            if not ticket:
                return json.dumps({"error": "Ticket not found"}, ensure_ascii=False)

            now = datetime.now(timezone.utc)
            sla_deadline = ticket.sla_deadline
            is_breached = sla_deadline and sla_deadline < now
            remaining_minutes = None
            if sla_deadline and not is_breached:
                remaining_minutes = int((sla_deadline - now).total_seconds() / 60)
            overdue_minutes = None
            if sla_deadline and is_breached:
                overdue_minutes = int((now - sla_deadline).total_seconds() / 60)

            sla_minutes = {
                "critical": settings.sla_critical_minutes,
                "high": settings.sla_high_minutes,
                "medium": settings.sla_medium_minutes,
                "low": settings.sla_low_minutes,
            }.get(ticket.urgency, settings.sla_medium_minutes)

            return json.dumps({
                "ticket_id": str(ticket.id),
                "ticket_no": ticket.ticket_no,
                "urgency": ticket.urgency,
                "sla_minutes": sla_minutes,
                "sla_deadline": sla_deadline.isoformat() if sla_deadline else None,
                "is_breached": is_breached,
                "remaining_minutes": remaining_minutes,
                "overdue_minutes": overdue_minutes,
            }, ensure_ascii=False)

    logger.info("MCP tools and resources registered for dispatch-agent")


async def register_to_consul():
    """Register this MCP server with Consul for service discovery."""
    import httpx
    _LOCAL_MODE = os.environ.get("LOCAL_MODE", "1") == "1"
    service_id = str(uuid.uuid4())
    payload = {
        "ID": service_id,
        "Name": "dispatch-agent",
        "Address": "localhost" if _LOCAL_MODE else "dispatch-agent",
        "Port": 8000,
        "Tags": ["mcp", "dispatch", "ticket"],
        "Check": {
            "HTTP": f"http://{'localhost' if _LOCAL_MODE else 'dispatch-agent'}:8000/health",
            "Interval": "10s",
            "Timeout": "3s",
        },
    }
    async with httpx.AsyncClient() as client:
        await client.put(f"{settings.consul_url}/v1/agent/service/register", json=payload)
    logger.info(f"Registered dispatch-agent with Consul (ID: {service_id})")


def _generate_ticket_no() -> str:
    """Generate a ticket number like WO-20240804-0001."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    import random
    suffix = str(random.randint(1, 9999)).zfill(4)
    return f"WO-{today}-{suffix}"