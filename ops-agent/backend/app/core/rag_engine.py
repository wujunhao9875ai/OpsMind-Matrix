"""RAG 引擎 - 混合检索（PGVector 向量 + BM25 → RRF → Rerank）"""
import time
from sqlalchemy import select
from app.config import settings
from app.database import async_session
from app.models.knowledge import KnowledgeChunk
from app.core.logger import setup_logger, log_event

logger = setup_logger("rag_engine")

# Lazy imports for optional dependencies
_bm25_retriever = None
_reranker = None


def _get_bm25():
    global _bm25_retriever
    if _bm25_retriever is None:
        try:
            from app.core.bm25_retriever import bm25_retriever as bm25
            _bm25_retriever = bm25
        except ImportError:
            log_event(logger, "bm25_unavailable", level="WARN")
            _bm25_retriever = False
    return _bm25_retriever if _bm25_retriever is not False else None


def _get_reranker():
    global _reranker
    if _reranker is None:
        try:
            from app.core.reranker import reranker as r
            _reranker = r
        except ImportError:
            log_event(logger, "reranker_unavailable", level="WARN")
            _reranker = False
    return _reranker if _reranker is not False else None


def rrf_fusion(dense_results: list[dict], sparse_results: list[dict], k: int = 60) -> list[dict]:
    """RRF 融合向量和 BM25 结果。"""
    score_map = {}
    for rank, doc in enumerate(dense_results):
        doc_id = doc.get("id")
        score_map[doc_id] = score_map.get(doc_id, 0) + 1 / (k + rank + 1)
    for rank, doc in enumerate(sparse_results):
        doc_id = doc.get("id")
        score_map[doc_id] = score_map.get(doc_id, 0) + 1 / (k + rank + 1)

    all_docs = {doc.get("id"): doc for doc in dense_results + sparse_results}
    merged = [(all_docs[doc_id], score) for doc_id, score in score_map.items() if doc_id in all_docs]
    merged.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in merged]


async def vector_search(query: str, top_k: int = 10) -> list[dict]:
    """PGVector 向量检索（余弦相似度）。"""
    try:
        from app.core.llm_adapter import llm_adapter
        query_embedding = llm_adapter.embed([query])[0]
    except Exception as e:
        log_event(logger, "embedding_error", level="ERROR", error=str(e))
        return []

    try:
        async with async_session() as db:
            distance = KnowledgeChunk.embedding.cosine_distance(query_embedding).label("distance")
            result = await db.execute(
                select(KnowledgeChunk, distance)
                .where(
                    KnowledgeChunk.chunk_type == "child",
                    KnowledgeChunk.embedding.isnot(None),
                )
                .order_by(distance)
                .limit(top_k)
            )
            docs = []
            for chunk, dist in result.all():
                docs.append({
                    "id": str(chunk.id),
                    "content": chunk.content,
                    "score": float(1 - dist),
                    "parent_text": chunk.parent_text or chunk.content,
                    "section_title": chunk.section_title or "",
                    "doc_id": str(chunk.doc_id),
                })
            return docs
    except Exception as e:
        log_event(logger, "vector_search_error", level="ERROR", error=str(e))
        return []


async def search_knowledge(query: str, top_k: int = 5) -> list[dict]:
    """混合检索：向量 + BM25 → RRF 融合 → Rerank 精排。"""
    start = time.time()

    # 向量检索
    dense_results = await vector_search(query, top_k=settings.dense_k)
    # 过滤相似度低于阈值的无关结果，避免污染上下文
    dense_results = [d for d in dense_results if d.get("score", 0) >= settings.similarity_threshold]
    log_event(logger, "dense_retrieval", query=query, result_count=len(dense_results), threshold=settings.similarity_threshold)

    # BM25 检索
    sparse_results = []
    bm25 = _get_bm25()
    if bm25 and not bm25.is_empty():
        sparse_results = bm25.search(query, top_k=settings.sparse_k)
    log_event(logger, "sparse_retrieval", query=query, result_count=len(sparse_results))

    # RRF 融合
    if dense_results and sparse_results:
        merged = rrf_fusion(dense_results, sparse_results)
    else:
        merged = dense_results or sparse_results
    log_event(logger, "rrf_fusion", query=query, result_count=len(merged))

    # Rerank 精排
    reranker = _get_reranker()
    if reranker:
        final = reranker.rerank(query, merged, top_k=top_k)
    else:
        final = merged[:top_k]
    log_event(logger, "rerank", query=query, result_count=len(final), duration_ms=(time.time() - start) * 1000)

    return final


def generate_rag_answer(query: str, context_docs: list[dict], history: list[dict] = None) -> str:
    """基于检索结果和对话历史生成 RAG 回答。"""
    from app.core.llm_adapter import llm_adapter
    from app.utils.prompts import RAG_QA_PROMPT

    if not context_docs:
        return "知识库中暂时没有找到与您问题相关的内容，请尝试更换关键词重新描述，或联系运维团队获取进一步帮助。"

    context_text = "\n\n---\n\n".join([
        f"[来源: {doc.get('section_title', '未知')}]\n{doc.get('parent_text', doc.get('content', ''))}"
        for doc in context_docs
    ])

    prompt_text = RAG_QA_PROMPT.format(context=context_text, question=query)

    # 构建消息列表，包含历史对话
    messages = []
    if history:
        for msg in history:
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": prompt_text})

    return llm_adapter.chat(messages)


async def stream_rag_answer(query: str, context_docs: list[dict]):
    """流式生成 RAG 回答，逐 token 返回。"""
    from app.core.llm_adapter import llm_adapter
    from app.utils.prompts import RAG_QA_PROMPT
    import httpx

    context_text = "\n\n---\n\n".join([
        f"[来源: {doc.get('section_title', '未知')}]\n{doc.get('parent_text', doc.get('content', ''))}"
        for doc in context_docs
    ])

    prompt_text = RAG_QA_PROMPT.format(context=context_text, question=query)
    async with httpx.AsyncClient(timeout=60) as client:
        async with client.stream(
            "POST",
            f"{llm_adapter.base_url}/chat/completions",
            headers=llm_adapter._headers(),
            json={
                "model": settings.llm_model,
                "messages": [{"role": "user", "content": prompt_text}],
                "stream": True,
            },
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    import json
                    try:
                        data = json.loads(data_str)
                        delta = data["choices"][0].get("delta", {})
                        if delta.get("content"):
                            yield delta["content"]
                    except json.JSONDecodeError:
                        continue