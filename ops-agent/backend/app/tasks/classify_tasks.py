from app.tasks.celery_app import celery_app
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import CATEGORY_CLASSIFY_PROMPT


@celery_app.task(bind=True, max_retries=3)
def classify_message_task(self, message_id: str, question: str, intent: str):
    """异步标注消息三级分类。"""
    import json
    try:
        prompt = CATEGORY_CLASSIFY_PROMPT.format(question=question, intent=intent)
        response = llm_adapter.chat_model.invoke(prompt)
        data = json.loads(response.content.strip())
        return data.get("category", f"{intent}-uncategorized")
    except json.JSONDecodeError:
        return f"{intent}-uncategorized"
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)