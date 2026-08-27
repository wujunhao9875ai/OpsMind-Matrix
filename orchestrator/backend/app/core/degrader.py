"""降级策略"""
DEGRADED_MESSAGES = {
    "ops-agent": "AI 引擎暂时繁忙，请稍后重试或联系人工客服。",
    "dispatch-agent": "工单系统暂时不可用，请稍后重试。",
    "warehouse-agent": "库房管理系统暂时不可用，请稍后重试。",
    "data-platform": "数据分析服务暂时不可用。",
    "all_down": "系统繁忙，请稍后重试或联系管理员。",
}

def get_degraded_message(agent_name: str = None) -> str:
    if agent_name:
        return DEGRADED_MESSAGES.get(agent_name, DEGRADED_MESSAGES["all_down"])
    return DEGRADED_MESSAGES["all_down"]