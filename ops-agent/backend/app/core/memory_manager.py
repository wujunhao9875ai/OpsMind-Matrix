from app.core.llm_adapter import llm_adapter
from app.utils.prompts import CONVERSATION_SUMMARY_PROMPT
from app.config import settings


def generate_summary(early_messages: list[dict]) -> str:
    """压缩早期对话为摘要。"""
    if not early_messages:
        return ""
    try:
        text = "\n".join([f"{m['role']}: {m['content']}" for m in early_messages])
        prompt = CONVERSATION_SUMMARY_PROMPT.format(early_messages=text)
        response = llm_adapter.chat_model.invoke(prompt)
        return response.content.strip()
    except Exception:
        return ""


def get_context_window(history: list[dict]) -> tuple[list[dict], list[dict]]:
    """返回滑动窗口：最近 N 轮原始消息 + 早期消息（用于摘要压缩）。"""
    max_recent = settings.max_recent_messages * 2  # 每轮 user + assistant
    if len(history) <= max_recent:
        return history, []
    recent = history[-max_recent:]
    early = history[:-max_recent]
    return recent, early