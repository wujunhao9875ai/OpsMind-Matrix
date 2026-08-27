try:
    import jieba
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False


class BM25Retriever:
    """BM25 关键词检索器，支持中文分词。"""

    def __init__(self):
        if not _BM25_AVAILABLE:
            raise ImportError("jieba and rank_bm25 are required for BM25 retrieval")
        self._index: "BM25Okapi | None" = None
        self._documents: list[dict] = []

    def build_index(self, documents: list[dict]):
        """构建 BM25 索引。documents: [{"id": str, "content": str}, ...]"""
        self._documents = documents
        tokenized = [list(jieba.cut(doc["content"])) for doc in documents]
        self._index = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """检索并返回带分数的文档列表。"""
        if self._index is None:
            return []
        tokenized_query = list(jieba.cut(query))
        scores = self._index.get_scores(tokenized_query)
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        max_score = max(scores) if max(scores) > 0 else 1
        for idx, score in indexed:
            if score > 0:
                results.append({
                    "id": self._documents[idx]["id"],
                    "content": self._documents[idx]["content"],
                    "score": score / max_score,
                    "doc_id": self._documents[idx].get("doc_id"),
                    "parent_text": self._documents[idx].get("parent_text"),
                })
        return results

    def is_empty(self) -> bool:
        return self._index is None or len(self._documents) == 0


bm25_retriever = BM25Retriever()