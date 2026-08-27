"""LangGraph 编排图 - 含 Harness 节点、熔断、重试、降级"""

import time
from typing import TypedDict, Optional, Annotated
from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph

from app.core.router import route_intent, INTENT_AGENT_MAP
from app.core.harness_node import (
    harness_preflight,
    harness_postflight,
    call_agent_with_harness,
    is_degraded_response,
)
from app.core.degrader import get_degraded_message
from app.core.logger import setup_logger, log_event
from app.core.tracer import generate_trace_id

logger = setup_logger("graph")


# ==================== State 定义 ====================

class OrchestratorState(TypedDict):
    """编排图状态"""
    # 输入
    message: str
    session_id: str
    context: list[dict]
    trace_id: str

    # 意图分类
    intent: str
    target_agent: str
    confidence: float

    # Agent 调用结果
    agent_results: dict          # {agent_name: {result, error, degraded, degraded_reason}}
    degraded_agents: list[str]   # 被降级的 agent 列表

    # 聚合
    reply: str
    sources: list

    # Harness
    preflight: dict
    postflight: dict
    all_degraded: bool
    node_timings: dict           # {node_name: duration_ms}
    total_duration_ms: float

    # 子图工作流结果
    workflow_results: dict       # {workflow_name: result}

    # 用户身份信息
    user_info: dict              # {username, role, ...}


# ==================== 意图分类节点 ====================

async def classify_intent_node(state: OrchestratorState) -> dict:
    """关键词快通道 → LLM 多意图 → 上下文感知 → 用户确认"""
    start = time.time()

    message = state["message"]
    session_id = state.get("session_id")
    trace_id = state.get("trace_id", "")

    route_result = route_intent(message, trace_id, session_id)
    intent = route_result["intent"]
    target_agent = route_result["target_agent"]

    # 简单置信度：关键词匹配命中为高置信度
    confidence = 0.85 if intent != "consult" else 0.6

    duration = round((time.time() - start) * 1000, 2)
    node_timings = state.get("node_timings", {})
    node_timings["classify_intent"] = duration

    log_event(logger, "intent_classified", trace_id=trace_id,
              intent=intent, agent=target_agent, confidence=confidence)

    return {
        "intent": intent,
        "target_agent": target_agent,
        "confidence": confidence,
        "node_timings": node_timings,
    }


# ==================== Agent 调用节点 ====================

def _make_agent_call_node(agent_name: str):
    """工厂函数：创建 Agent 调用节点（返回闭包，非协程）"""

    async def node(state: OrchestratorState) -> dict:
        start = time.time()
        trace_id = state.get("trace_id", "")
        message = state["message"]
        session_id = state.get("session_id", "")
        context = state.get("context", [])
        user_info = state.get("user_info", {})

        result = await call_agent_with_harness(
            agent_name=agent_name,
            tool_name="chat_reply",
            arguments={
                "message": message,
                "query": message,
                "conversation_id": session_id,
                "history": context,
                "user_info": user_info,
            },
            trace_id=trace_id,
        )

        duration = round((time.time() - start) * 1000, 2)
        node_timings = state.get("node_timings", {})
        node_timings[f"call_{agent_name.replace('-', '_')}"] = duration

        agent_results = state.get("agent_results", {})
        agent_results[agent_name] = result

        degraded_agents = state.get("degraded_agents", [])
        if result.get("degraded"):
            degraded_agents = degraded_agents + [agent_name]

        # 提取回复
        reply = ""
        sources = []
        if result.get("result"):
            data = result["result"]
            reply = data.get("reply", "") or data.get("answer", "") or str(data)
            sources = data.get("sources", [])

        return {
            "agent_results": agent_results,
            "degraded_agents": degraded_agents,
            "reply": reply,
            "sources": sources,
            "node_timings": node_timings,
        }

    return node


# ==================== 子图：repair_workflow ====================

async def repair_workflow_node(state: OrchestratorState) -> dict:
    """报修工作流: ops-agent → dispatch-agent"""
    start = time.time()
    trace_id = state.get("trace_id", "")
    message = state["message"]
    session_id = state.get("session_id", "")
    context = state.get("context", [])
    agent_results = state.get("agent_results", {})
    user_info = state.get("user_info", {})

    # Step 1: ops-agent 诊断
    ops_result = await call_agent_with_harness(
        agent_name="ops-agent",
        tool_name="chat_reply",
        arguments={
            "message": message,
            "query": message,
            "conversation_id": session_id,
            "history": context,
            "user_info": user_info,
        },
        trace_id=trace_id,
    )
    agent_results["ops-agent"] = ops_result

    degraded_agents = state.get("degraded_agents", [])
    if ops_result.get("degraded"):
        degraded_agents = degraded_agents + ["ops-agent"]

    # Step 2: dispatch-agent 创建工单
    dispatch_result = await call_agent_with_harness(
        agent_name="dispatch-agent",
        tool_name="chat_reply",
        arguments={
            "message": message,
            "query": message,
            "conversation_id": session_id,
            "history": context,
            "user_info": user_info,
        },
        trace_id=trace_id,
    )
    agent_results["dispatch-agent"] = dispatch_result
    if dispatch_result.get("degraded"):
        degraded_agents = degraded_agents + ["dispatch-agent"]

    reply = ""
    sources = []
    if ops_result.get("result"):
        data = ops_result["result"]
        reply = data.get("reply", "") or data.get("answer", "")
        sources = data.get("sources", [])
    if dispatch_result.get("result"):
        data = dispatch_result["result"]
        dispatch_reply = data.get("reply", "") or data.get("answer", "")
        if dispatch_reply:
            reply = reply + "\n\n" + dispatch_reply if reply else dispatch_reply

    duration = round((time.time() - start) * 1000, 2)
    node_timings = state.get("node_timings", {})
    node_timings["repair_workflow"] = duration

    return {
        "agent_results": agent_results,
        "degraded_agents": degraded_agents,
        "reply": reply,
        "sources": sources,
        "node_timings": node_timings,
    }


# ==================== 子图：spare_workflow ====================

async def spare_workflow_node(state: OrchestratorState) -> dict:
    """备件工作流: dispatch-agent → warehouse-agent"""
    start = time.time()
    trace_id = state.get("trace_id", "")
    message = state["message"]
    session_id = state.get("session_id", "")
    context = state.get("context", [])
    agent_results = state.get("agent_results", {})
    user_info = state.get("user_info", {})

    dispatch_result = await call_agent_with_harness(
        agent_name="dispatch-agent",
        tool_name="chat_reply",
        arguments={
            "message": message,
            "query": message,
            "conversation_id": session_id,
            "history": context,
            "user_info": user_info,
        },
        trace_id=trace_id,
    )
    agent_results["dispatch-agent"] = dispatch_result

    degraded_agents = state.get("degraded_agents", [])
    if dispatch_result.get("degraded"):
        degraded_agents = degraded_agents + ["dispatch-agent"]

    warehouse_result = await call_agent_with_harness(
        agent_name="warehouse-agent",
        tool_name="chat_reply",
        arguments={
            "message": message,
            "query": message,
            "conversation_id": session_id,
            "history": context,
        },
        trace_id=trace_id,
    )
    agent_results["warehouse-agent"] = warehouse_result
    if warehouse_result.get("degraded"):
        degraded_agents = degraded_agents + ["warehouse-agent"]

    reply = ""
    sources = []
    if dispatch_result.get("result"):
        data = dispatch_result["result"]
        reply = data.get("reply", "") or data.get("answer", "")
        sources = data.get("sources", [])
    if warehouse_result.get("result"):
        data = warehouse_result["result"]
        wh_reply = data.get("reply", "") or data.get("answer", "")
        if wh_reply:
            reply = reply + "\n\n" + wh_reply if reply else wh_reply

    duration = round((time.time() - start) * 1000, 2)
    node_timings = state.get("node_timings", {})
    node_timings["spare_workflow"] = duration

    return {
        "agent_results": agent_results,
        "degraded_agents": degraded_agents,
        "reply": reply,
        "sources": sources,
        "node_timings": node_timings,
    }


# ==================== 子图：device_repair_workflow ====================

async def device_repair_workflow_node(state: OrchestratorState) -> dict:
    """设备维修工单: warehouse-agent → dispatch-agent"""
    start = time.time()
    trace_id = state.get("trace_id", "")
    message = state["message"]
    session_id = state.get("session_id", "")
    context = state.get("context", [])
    agent_results = state.get("agent_results", {})
    user_info = state.get("user_info", {})

    warehouse_result = await call_agent_with_harness(
        agent_name="warehouse-agent",
        tool_name="chat_reply",
        arguments={
            "message": message,
            "query": message,
            "conversation_id": session_id,
            "history": context,
            "user_info": user_info,
        },
        trace_id=trace_id,
    )
    agent_results["warehouse-agent"] = warehouse_result

    degraded_agents = state.get("degraded_agents", [])
    if warehouse_result.get("degraded"):
        degraded_agents = degraded_agents + ["warehouse-agent"]

    dispatch_result = await call_agent_with_harness(
        agent_name="dispatch-agent",
        tool_name="chat_reply",
        arguments={
            "message": message,
            "query": message,
            "conversation_id": session_id,
            "history": context,
            "user_info": user_info,
        },
        trace_id=trace_id,
    )
    agent_results["dispatch-agent"] = dispatch_result
    if dispatch_result.get("degraded"):
        degraded_agents = degraded_agents + ["dispatch-agent"]

    reply = ""
    sources = []
    if warehouse_result.get("result"):
        data = warehouse_result["result"]
        reply = data.get("reply", "") or data.get("answer", "")
        sources = data.get("sources", [])
    if dispatch_result.get("result"):
        data = dispatch_result["result"]
        dp_reply = data.get("reply", "") or data.get("answer", "")
        if dp_reply:
            reply = reply + "\n\n" + dp_reply if reply else dp_reply

    duration = round((time.time() - start) * 1000, 2)
    node_timings = state.get("node_timings", {})
    node_timings["device_repair_workflow"] = duration

    return {
        "agent_results": agent_results,
        "degraded_agents": degraded_agents,
        "reply": reply,
        "sources": sources,
        "node_timings": node_timings,
    }


# ==================== LLM 聚合节点 ====================

async def llm_aggregate_node(state: OrchestratorState) -> dict:
    """多结果聚合 + 降级信息"""
    start = time.time()
    trace_id = state.get("trace_id", "")

    degraded_agents = state.get("degraded_agents", [])
    agent_results = state.get("agent_results", {})
    reply = state.get("reply", "")

    # 如果有降级 agent，在回复中附加提示
    if degraded_agents:
        degraded_msgs = []
        for agent_name in degraded_agents:
            degraded_msgs.append(get_degraded_message(agent_name))
        if degraded_msgs:
            degraded_note = "\n\n---\n> " + "\n> ".join(degraded_msgs)
            reply = reply + degraded_note if reply else degraded_msgs[0]

    duration = round((time.time() - start) * 1000, 2)
    node_timings = state.get("node_timings", {})
    node_timings["llm_aggregate"] = duration

    log_event(logger, "llm_aggregated", trace_id=trace_id,
              degraded_agents=degraded_agents,
              has_reply=bool(reply))

    return {
        "reply": reply,
        "node_timings": node_timings,
    }


# ==================== LLM 降级节点 ====================

async def llm_fallback_node(state: OrchestratorState) -> dict:
    """意图置信度低时直接走 LLM"""
    start = time.time()
    trace_id = state.get("trace_id", "")
    message = state["message"]
    context = state.get("context", [])
    intent = state.get("intent", "consult")

    from app.api.chat import _llm_fallback
    reply = await _llm_fallback(message, context, intent, "ops-agent")

    duration = round((time.time() - start) * 1000, 2)
    node_timings = state.get("node_timings", {})
    node_timings["llm_fallback"] = duration

    return {
        "reply": reply,
        "node_timings": node_timings,
    }


# ==================== 全局降级节点 ====================

async def global_degraded_node(state: OrchestratorState) -> dict:
    """全部 Agent 不可用时的全局降级"""
    log_event(logger, "global_degraded", trace_id=state.get("trace_id", ""))
    return {
        "reply": get_degraded_message("all_down"),
        "degraded_agents": list(state.get("preflight", {}).get("unavailable_agents", [])),
    }


# ==================== 路由函数 ====================

def _last_assistant_content(context) -> str:
    """返回上下文里最后一条 assistant 消息的内容。"""
    for m in reversed(context or []):
        if isinstance(m, dict) and m.get("role") == "assistant":
            return m.get("content", "")
    return ""


def _route_after_preflight(state: OrchestratorState) -> str:
    """preflight 后路由：全部不可用走 global_degraded，否则进入 classify_intent"""
    if state.get("all_degraded", False):
        return "global_degraded"
    return "classify_intent"


def _route_after_classify(state: OrchestratorState) -> str:
    """意图分类后路由：低置信度走 llm_fallback，否则路由到对应 Agent"""
    confidence = state.get("confidence", 0)
    if confidence < 0.5:
        return "llm_fallback"

    intent = state.get("intent", "consult")
    message = state.get("message", "")

    # 报修场景中，确认类消息（"好的"、"需要"等）直接路由到 dispatch-agent，
    # 避免 repair_workflow 再调用 ops-agent 产生无关回复
    if intent == "repair":
        # 多轮信息补全：上一轮在追问位置/联系方式，本轮是对应的回答 → 直接路由 dispatch-agent
        last_assistant = _last_assistant_content(state.get("context", []))
        if "请告诉我设备所在的位置" in last_assistant or "请提供您的联系方式" in last_assistant:
            return "call_dispatch_agent"

        # 用户明确要求工程师上门/派人，或显式"报修/生成工单/创建工单/提交工单" → 直接创建工单，跳过诊断
        engineer_request_keywords = ["需要工程师", "工程师上门", "需要人", "派人来", "派人", "上门",
                                     "报修", "生成工单", "创建工单", "提交工单"]
        if any(kw in message for kw in engineer_request_keywords):
            return "call_dispatch_agent"

        confirm_keywords = ["需要", "是", "好的", "可以", "确认", "行", "嗯", "对"]
        repair_keywords = ["报修", "帮我", "帮忙", "故障", "坏了", "不能用", "出问题", "不工作", "卡纸", "连不上", "打不开", "没反应", "需要工程师", "需要人", "派人来", "上门"]
        rejection_keywords = ["不需要", "不用", "不要", "不了", "不必", "算了", "不用了", "先不"]
        if any(kw in message for kw in rejection_keywords):
            return "call_dispatch_agent"  # 由 dispatch-agent 处理拒绝
        if any(kw in message for kw in confirm_keywords) and not any(kw in message for kw in repair_keywords):
            return "call_dispatch_agent"

    # 意图 → 节点映射
    INTENT_NODE_MAP = {
        "consult": "call_ops_agent",
        "repair": "repair_workflow",
        "check_progress": "call_dispatch_agent",
        "ticket_manage": "call_dispatch_agent",
        "warehouse_op": "call_warehouse_agent",
        "spare_request": "spare_workflow",
        "query_stats": "call_dispatch_agent",
        "data_query": "call_data_platform",
    }

    return INTENT_NODE_MAP.get(intent, "call_ops_agent")


# ==================== 构建图 ====================

def build_orchestrator_graph() -> CompiledStateGraph:
    """构建完整的编排图"""

    graph = StateGraph(OrchestratorState)

    # 添加节点
    graph.add_node("harness_preflight", harness_preflight)
    graph.add_node("classify_intent", classify_intent_node)
    graph.add_node("call_ops_agent", _make_agent_call_node("ops-agent"))
    graph.add_node("call_dispatch_agent", _make_agent_call_node("dispatch-agent"))
    graph.add_node("call_warehouse_agent", _make_agent_call_node("warehouse-agent"))
    graph.add_node("call_data_platform", _make_agent_call_node("data-platform"))
    graph.add_node("repair_workflow", repair_workflow_node)
    graph.add_node("spare_workflow", spare_workflow_node)
    graph.add_node("device_repair_workflow", device_repair_workflow_node)
    graph.add_node("llm_aggregate", llm_aggregate_node)
    graph.add_node("llm_fallback", llm_fallback_node)
    graph.add_node("global_degraded", global_degraded_node)
    graph.add_node("harness_postflight", harness_postflight)

    # 设置入口
    graph.set_entry_point("harness_preflight")

    # harness_preflight 条件路由
    graph.add_conditional_edges(
        "harness_preflight",
        _route_after_preflight,
        {
            "global_degraded": "global_degraded",
            "classify_intent": "classify_intent",
        }
    )

    # global_degraded → END
    graph.add_edge("global_degraded", "harness_postflight")

    # classify_intent 条件路由
    graph.add_conditional_edges(
        "classify_intent",
        _route_after_classify,
        {
            "llm_fallback": "llm_fallback",
            "call_ops_agent": "call_ops_agent",
            "call_dispatch_agent": "call_dispatch_agent",
            "call_warehouse_agent": "call_warehouse_agent",
            "call_data_platform": "call_data_platform",
            "repair_workflow": "repair_workflow",
            "spare_workflow": "spare_workflow",
        }
    )

    # 所有 Agent 节点 → llm_aggregate
    graph.add_edge("call_ops_agent", "llm_aggregate")
    graph.add_edge("call_dispatch_agent", "llm_aggregate")
    graph.add_edge("call_warehouse_agent", "llm_aggregate")
    graph.add_edge("call_data_platform", "llm_aggregate")
    graph.add_edge("repair_workflow", "llm_aggregate")
    graph.add_edge("spare_workflow", "llm_aggregate")
    graph.add_edge("device_repair_workflow", "llm_aggregate")
    graph.add_edge("llm_fallback", "llm_aggregate")

    # llm_aggregate → harness_postflight → END
    graph.add_edge("llm_aggregate", "harness_postflight")
    graph.add_edge("harness_postflight", END)

    return graph.compile()


# 全局单例
_orchestrator_graph: Optional[CompiledStateGraph] = None


def get_orchestrator_graph() -> CompiledStateGraph:
    """获取编译后的编排图单例"""
    global _orchestrator_graph
    if _orchestrator_graph is None:
        _orchestrator_graph = build_orchestrator_graph()
    return _orchestrator_graph


async def run_orchestrator(
    message: str,
    session_id: str,
    context: list[dict],
    trace_id: str = None,
    user_info: dict = None,
) -> dict:
    """运行编排图

    Returns:
        {"reply": str, "intent": str, "agent": str, "confidence": float,
         "sources": list, "degraded_agents": list, "preflight": dict,
         "postflight": dict, "trace_id": str, "total_duration_ms": float}
    """
    if trace_id is None:
        trace_id = generate_trace_id()

    graph = get_orchestrator_graph()

    initial_state: OrchestratorState = {
        "message": message,
        "session_id": session_id,
        "context": context,
        "trace_id": trace_id,
        "intent": "",
        "target_agent": "",
        "confidence": 0.0,
        "agent_results": {},
        "degraded_agents": [],
        "reply": "",
        "sources": [],
        "preflight": {},
        "postflight": {},
        "all_degraded": False,
        "node_timings": {},
        "total_duration_ms": 0.0,
        "workflow_results": {},
        "user_info": user_info or {},
    }

    total_start = time.time()
    final_state = await graph.ainvoke(initial_state)
    total_duration = round((time.time() - total_start) * 1000, 2)

    return {
        "reply": final_state.get("reply", ""),
        "intent": final_state.get("intent", ""),
        "agent": final_state.get("target_agent", ""),
        "confidence": final_state.get("confidence", 0.0),
        "sources": final_state.get("sources", []),
        "degraded_agents": final_state.get("degraded_agents", []),
        "preflight": final_state.get("preflight", {}),
        "postflight": final_state.get("postflight", {}),
        "trace_id": trace_id,
        "total_duration_ms": total_duration,
    }