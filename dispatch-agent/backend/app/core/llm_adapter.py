from langchain_openai import ChatOpenAI
from app.config import settings


class LLMAdapter:
    """LLM 适配器，用于 Admin NLU 意图识别。"""

    def __init__(self):
        self._chat_model = None

    @property
    def chat_model(self) -> ChatOpenAI:
        if self._chat_model is None:
            self._chat_model = ChatOpenAI(
                model=settings.llm_model,
                base_url=settings.siliconflow_base_url,
                api_key=settings.siliconflow_api_key,
                temperature=0.1,
                timeout=60,
            )
        return self._chat_model


llm_adapter = LLMAdapter()