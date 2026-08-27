"""设备生命周期状态机 - LangGraph 定义

设备状态流转:
  in_stock → allocated → in_use → damaged → in_repair → repaired → in_stock
                                   damaged → scrapped
                                   repaired → scrapped
  in_stock → scrapped

LangGraph StateGraph 定义 7 状态及转换规则，确保所有设备操作合法且可追踪。
"""
from datetime import datetime, timezone, date
from enum import Enum
from typing import TypedDict
from langgraph.graph import StateGraph, END
import uuid


# ---- Device Status & Action Enums ----

class DeviceStatus(str, Enum):
    IN_STOCK = "in_stock"
    ALLOCATED = "allocated"
    IN_USE = "in_use"
    DAMAGED = "damaged"
    IN_REPAIR = "in_repair"
    REPAIRED = "repaired"
    SCRAPPED = "scrapped"


class DeviceAction(str, Enum):
    ALLOCATE = "allocate"
    SCRAP = "scrap"
    DELIVER = "deliver"
    CANCEL_ALLOCATE = "cancel_allocate"
    RETURN_DAMAGED = "return_damaged"
    SEND_REPAIR = "send_repair"
    REPAIR_DONE = "repair_done"
    RESTOCK = "restock"


# ---- LangGraph State Definition ----

class DeviceGraphState(TypedDict):
    """设备状态图的内部状态"""
    current_status: str
    action: str
    next_status: str
    error: str | None


# ---- 状态转换规则 ----

DEVICE_TRANSITIONS: dict[str, dict[str, str]] = {
    DeviceStatus.IN_STOCK: {
        DeviceAction.ALLOCATE: DeviceStatus.ALLOCATED,
        DeviceAction.SCRAP: DeviceStatus.SCRAPPED,
    },
    DeviceStatus.ALLOCATED: {
        DeviceAction.DELIVER: DeviceStatus.IN_USE,
        DeviceAction.CANCEL_ALLOCATE: DeviceStatus.IN_STOCK,
    },
    DeviceStatus.IN_USE: {
        DeviceAction.RETURN_DAMAGED: DeviceStatus.DAMAGED,
    },
    DeviceStatus.DAMAGED: {
        DeviceAction.SEND_REPAIR: DeviceStatus.IN_REPAIR,
        DeviceAction.SCRAP: DeviceStatus.SCRAPPED,
    },
    DeviceStatus.IN_REPAIR: {
        DeviceAction.REPAIR_DONE: DeviceStatus.REPAIRED,
    },
    DeviceStatus.REPAIRED: {
        DeviceAction.RESTOCK: DeviceStatus.IN_STOCK,
        DeviceAction.SCRAP: DeviceStatus.SCRAPPED,
    },
}

TERMINAL_STATES = {DeviceStatus.SCRAPPED}


# ---- Exception Classes ----

class InvalidStateError(Exception):
    """状态非法（终态）"""
    pass


class InvalidTransitionError(Exception):
    """状态转换非法"""
    pass


# ---- LangGraph State Machine ----

def _transition_node(state: DeviceGraphState) -> DeviceGraphState:
    """LangGraph 节点：处理设备状态转换"""
    current = state["current_status"]
    action = state["action"]

    if current in TERMINAL_STATES:
        return {
            "current_status": current,
            "action": action,
            "next_status": current,
            "error": f"状态 '{current}' 为终态，不可变更",
        }
    if current not in DEVICE_TRANSITIONS:
        return {
            "current_status": current,
            "action": action,
            "next_status": current,
            "error": f"未知状态: '{current}'",
        }
    if action not in DEVICE_TRANSITIONS[current]:
        available = list(DEVICE_TRANSITIONS[current].keys())
        return {
            "current_status": current,
            "action": action,
            "next_status": current,
            "error": f"设备无法从 '{current}' 执行 '{action}'，可用操作: {available}",
        }

    return {
        "current_status": current,
        "action": action,
        "next_status": DEVICE_TRANSITIONS[current][action],
        "error": None,
    }


def _build_device_graph() -> StateGraph:
    """构建 LangGraph 设备状态图"""
    workflow = StateGraph(DeviceGraphState)
    workflow.add_node("process_transition", _transition_node)
    workflow.set_entry_point("process_transition")
    workflow.add_edge("process_transition", END)
    return workflow.compile()


# 编译后的状态图实例
device_graph = _build_device_graph()


# ---- Public API (保持向后兼容) ----

def get_available_actions(current_status: str) -> list[str]:
    """获取当前状态可用的操作列表"""
    if current_status in DEVICE_TRANSITIONS:
        return list(DEVICE_TRANSITIONS[current_status].keys())
    return []


def get_next_status(current_status: str, action: str) -> str:
    """获取操作后的下一状态（通过 LangGraph 状态图）"""
    result = device_graph.invoke({
        "current_status": current_status,
        "action": action,
        "next_status": "",
        "error": None,
    })
    if result["error"]:
        if "终态" in result["error"] or "未知状态" in result["error"]:
            raise InvalidStateError(result["error"])
        raise InvalidTransitionError(result["error"])
    return result["next_status"]


def build_device_log(device_id: uuid.UUID, action: str, from_status: str,
                     to_status: str, operator_id: uuid.UUID,
                     related_ticket_id: uuid.UUID | None = None,
                     repair_vendor: str | None = None,
                     repair_cost: float | None = None,
                     expected_return_date: date | None = None,
                     comment: str | None = None) -> dict:
    """构建设备操作日志数据"""
    return {
        "device_id": device_id,
        "action": action,
        "from_status": from_status,
        "to_status": to_status,
        "operator_id": operator_id,
        "related_ticket_id": related_ticket_id,
        "repair_vendor": repair_vendor,
        "repair_cost": repair_cost,
        "expected_return_date": expected_return_date,
        "comment": comment,
        "created_at": datetime.now(timezone.utc),
    }