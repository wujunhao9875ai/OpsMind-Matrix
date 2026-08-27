import pytest
import asyncio
from app.core.intent_classifier import classify_intent
from app.core.rag_engine import search_knowledge
from app.utils.metrics import calculate_mrr
from tests.conftest import BAD_CASES


@pytest.mark.unit
def test_intent_classification():
    """验证意图分类在 Bad Case 上的表现（仅规则匹配，不调用 LLM）。"""
    repair_cases = [c for c in BAD_CASES if c["expected_route"] == "repair"]
    for case in repair_cases:
        intent = classify_intent(case["query"])
        assert intent == "repair", f"Case {case['id']}: expected repair, got {intent}"

    # unknown case 由规则匹配（无匹配关键词时会 fallback 到 LLM），
    # 标记为 integration 测试，仅在连接外部服务时运行
    unknown_cases = [c for c in BAD_CASES if c["expected_route"] == "unknown"]
    for case in unknown_cases:
        intent = classify_intent(case["query"])
        assert intent == "unknown", f"Case {case['id']}: expected unknown, got {intent}"


@pytest.mark.integration
def test_rag_retrieval_mrr():
    """验证 RAG 检索的 MRR 指标（需要 PostgreSQL + PGVector + vLLM 服务运行）。"""
    rag_cases = [c for c in BAD_CASES if c["expected_route"] == "rag"]
    mrr = asyncio.run(calculate_mrr(rag_cases, search_knowledge))
    assert mrr > 0.0, f"MRR should be > 0, got {mrr}"