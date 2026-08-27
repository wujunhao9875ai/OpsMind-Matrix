import httpx
from app.config import settings
from app.core.logger import setup_logger, log_event

logger = setup_logger("reranker")


class Reranker:
    """硅基流动 Reranker API 重排序器。"""

    def __init__(self):
        self._available = True

    def rerank(self, query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
        """通过硅基流动 Rerank API 对文档列表重排序。"""
        if not documents:
            return documents

        try:
            resp = httpx.post(
                f"{settings.siliconflow_base_url}/rerank",
                json={
                    "model": settings.reranker_model,
                    "query": query,
                    "documents": [doc["content"] for doc in documents],
                    "top_n": top_k,
                },
                headers={"Authorization": f"Bearer {settings.siliconflow_api_key}"},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("results", []):
                idx = item["index"]
                doc = documents[idx].copy()
                doc["rerank_score"] = item["relevance_score"]
                results.append(doc)
            return results[:top_k]
        except Exception as e:
            # Rerank 失败时回退到原始排序，记录日志便于排查
            log_event(logger, "rerank_fallback", level="WARN", error=str(e), query=query)
            for doc in documents:
                doc["rerank_score"] = doc.get("score", 0)
            return documents[:top_k]


reranker = Reranker()