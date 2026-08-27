import json
import re
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import ADMIN_NLU_PROMPT


ADMIN_INTENTS = [
    "create_ticket",
    "assign_ticket",
    "reassign_ticket",
    "query_ticket",
    "cancel_ticket",
    "priority_change",
    "query_stats",
]


def parse_admin_input(message: str) -> dict:
    prompt = ADMIN_NLU_PROMPT.format(message=message)
    try:
        response = llm_adapter.chat_model.invoke(prompt)
        content = response.content.strip()
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            result = json.loads(json_match.group())
            intent = result.get("intent", "unknown")
            slots = result.get("slots", {})
            if intent in ADMIN_INTENTS:
                return {"intent": intent, "slots": slots}
    except Exception:
        pass
    return {"intent": "unknown", "slots": {}}