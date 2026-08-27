from app.core.llm_adapter import llm_adapter
from app.utils.prompts import QUERY_REWRITE_PROMPT, MULTI_QUERY_PROMPT


def rewrite_query(question: str, history_summary: str = "") -> str:
    """结合对话历史改写用户问题，补全指代、术语化。"""
    if not history_summary:
        return question
    try:
        prompt = QUERY_REWRITE_PROMPT.format(history_summary=history_summary, question=question)
        response = llm_adapter.chat_model.invoke(prompt)
        return response.content.strip()
    except Exception:
        return question


def expand_multi_query(question: str) -> list[str]:
    """将复杂问题拆分为多个检索角度。"""
    try:
        prompt = MULTI_QUERY_PROMPT.format(question=question)
        response = llm_adapter.chat_model.invoke(prompt)
        queries = [q.strip() for q in response.content.strip().split("\n") if q.strip()]
        return queries if queries else [question]
    except Exception:
        return [question]