from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from app.config import settings


class LLMAdapter:
    """LLM 适配器，封装硅基流动 API 调用。"""

    def __init__(self):
        self._chat_model = None
        self._embedding_model = None

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

    @property
    def embedding_model(self) -> OpenAIEmbeddings:
        if self._embedding_model is None:
            self._embedding_model = OpenAIEmbeddings(
                model=settings.embedding_model,
                base_url=settings.siliconflow_base_url,
                api_key=settings.siliconflow_api_key,
                request_timeout=120,
            )
        return self._embedding_model


llm_adapter = LLMAdapter()