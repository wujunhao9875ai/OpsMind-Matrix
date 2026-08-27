"""工单状态机 - LangGraph 定义 6 状态

工单生命周期（6 状态）:
  created → assigned → in_progress → resolved → closed
     ↓         ↓           ↓
  cancelled  created    assigned (reassign/escalate/transfer)
                       cancelled (取消)
              closed ← reopened

LangGraph StateGraph 定义状态转换规则，确保所有转换合法且可追踪。
"""
from typing import TypedDict
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END
from app.config import settings


# ---- LangGraph State Definition ----

class TicketGraphState(TypedDict):
    """工单状态图的内部状态"""
    current_status: str
    action: str
    next_status: str
    error: str | None


# ---- 状态转换规则 ----

VALID_TRANSITIONS: dict[str, list[str]] = {
    "created": ["assign", "cancel"],
    "assigned": ["accept", "reject", "reassign", "transfer", "cancel"],
    "in_progress": ["resolve", "reassign", "escalate", "transfer"],
    "resolved": ["close", "reopen"],
    "closed": ["reopen"],
    "cancelled": [],
}

ACTION_TO_STATUS: dict[str, str] = {
    "assign": "assigned",
    "cancel": "cancelled",
    "accept": "in_progress",
    "reject": "created",
    "reassign": "assigned",
    "transfer": "assigned",
    "resolve": "resolved",
    "close": "closed",
    "reopen": "in_progress",
    "escalate": "assigned",
}


# ---- LangGraph State Machine ----

def _transition_node(state: TicketGraphState) -> TicketGraphState:
    """LangGraph 节点：处理状态转换"""
    current = state["current_status"]
    action = state["action"]
    allowed = VALID_TRANSITIONS.get(current, [])
    if action in allowed:
        return {
            "current_status": current,
            "action": action,
            "next_status": ACTION_TO_STATUS[action],
            "error": None,
        }
    return {
        "current_status": current,
        "action": action,
        "next_status": current,
        "error": f"Invalid transition: {current} -> {action}",
    }


def _build_ticket_graph() -> StateGraph:
    """构建 LangGraph 工单状态图"""
    workflow = StateGraph(TicketGraphState)
    workflow.add_node("process_transition", _transition_node)
    workflow.set_entry_point("process_transition")
    workflow.add_edge("process_transition", END)
    return workflow.compile()


# 编译后的状态图实例
ticket_graph = _build_ticket_graph()


# ---- Public API (保持向后兼容) ----

def calculate_sla_deadline(urgency: str) -> datetime:
    """计算 SLA 截止时间"""
    minutes_map = {
        "critical": settings.sla_critical_minutes,
        "high": settings.sla_high_minutes,
        "medium": settings.sla_medium_minutes,
        "low": settings.sla_low_minutes,
    }
    minutes = minutes_map.get(urgency, settings.sla_medium_minutes)
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def validate_transition(current_status: str, action: str) -> bool:
    """验证状态转换是否合法（通过 LangGraph 状态图）"""
    result = ticket_graph.invoke({
        "current_status": current_status,
        "action": action,
        "next_status": "",
        "error": None,
    })
    return result["error"] is None


def get_next_status(current_status: str, action: str) -> str:
    """获取操作后的下一状态（通过 LangGraph 状态图）"""
    result = ticket_graph.invoke({
        "current_status": current_status,
        "action": action,
        "next_status": "",
        "error": None,
    })
    if result["error"]:
        raise ValueError(result["error"])
    return result["next_status"]