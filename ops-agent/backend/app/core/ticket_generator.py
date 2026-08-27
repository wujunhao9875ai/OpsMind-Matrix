import json
import re
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import TICKET_EXTRACT_PROMPT


def generate_pre_ticket(conversation_text: str) -> dict:
    """从对话文本中提取工单信息，返回结构化 JSON。"""
    prompt = TICKET_EXTRACT_PROMPT.format(conversation=conversation_text)
    response = llm_adapter.chat_model.invoke(prompt)
    content = response.content.strip()

    # 提取 JSON 块
    json_match = re.search(r"\{[\s\S]*\}", content)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {
        "summary": "无法提取",
        "fault_category": "other",
        "urgency": "medium",
        "device_info": {},
        "location": "",
        "missing_info": ["自动提取失败，需人工补充"],
    }