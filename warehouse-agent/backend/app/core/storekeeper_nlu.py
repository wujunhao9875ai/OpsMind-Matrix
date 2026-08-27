"""库管员 NLU — 意图分类 + 槽位提取"""
import json
import re
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import STOREKEEPER_NLU_PROMPT


STOREKEEPER_INTENTS = [
    "stock_in",
    "stock_out",
    "device_in",
    "device_out",
    "transfer",
    "check_stock",
    "check_device",
    "scrap",
    "send_repair",
    "query_stats",
]

MAX_INPUT_LENGTH = 500


def parse_storekeeper_input(message: str) -> dict:
    """解析库管员自然语言输入，返回意图和槽位"""
    if not message or not isinstance(message, str):
        return {"intent": "unknown", "slots": {}}

    message = message.strip()[:MAX_INPUT_LENGTH]

    if not message:
        return {"intent": "unknown", "slots": {}}

    prompt = STOREKEEPER_NLU_PROMPT.format(message=message)
    try:
        response = llm_adapter.chat_model.invoke(prompt)
        content = response.content.strip()
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            result = json.loads(json_match.group())
            intent = result.get("intent", "unknown")
            slots = result.get("slots", {})
            if intent in STOREKEEPER_INTENTS:
                return {"intent": intent, "slots": slots}
    except Exception:
        pass
    return {"intent": "unknown", "slots": {}}