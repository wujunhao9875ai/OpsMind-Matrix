"""全局意图路由"""
import re
from app.core.intent_classifier import classify_intent
from app.core.logger import setup_logger, log_event

logger = setup_logger("router")

# Intent → Agent mapping
INTENT_AGENT_MAP = {
    "consult": "ops-agent",
    "repair": "dispatch-agent",
    "check_progress": "dispatch-agent",
    "ticket_manage": "dispatch-agent",
    "warehouse_op": "warehouse-agent",
    "spare_request": "dispatch-agent",
    "query_stats": "dispatch-agent",
    "data_query": "data-platform",
}

# 会话级别的意图状态（简单内存缓存，生产环境应使用 Redis）
_session_intent: dict[str, str] = {}


def route_intent(message: str, trace_id: str = None, session_id: str = None) -> dict:
    """Route user message to the appropriate agent based on intent.
    
    支持会话级别意图追踪：如果会话中已有 repair 意图，后续消息保持 repair。
    """
    # 检查会话中是否已有活跃的报修意图
    if session_id and session_id in _session_intent:
        cached_intent = _session_intent[session_id]
        # 如果是报修场景的追问，保持 repair 意图
        if cached_intent == "repair":
            intent = classify_intent(message)
            # 如果新消息不是明确的其他意图，保持 repair
            if intent in ("consult", "repair"):
                intent = "repair"
        else:
            intent = classify_intent(message)
    else:
        intent = classify_intent(message)

    # 存储会话意图
    if session_id:
        _session_intent[session_id] = intent

    target_agent = INTENT_AGENT_MAP.get(intent, "ops-agent")
    log_event(logger, "intent_routed", trace_id=trace_id, intent=intent, target_agent=target_agent, message=message[:100])
    return {"intent": intent, "target_agent": target_agent}


def clear_session_intent(session_id: str):
    """清除会话意图状态"""
    _session_intent.pop(session_id, None)