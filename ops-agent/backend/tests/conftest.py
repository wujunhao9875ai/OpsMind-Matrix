import pytest
from app.core.rag_engine import search_knowledge

BAD_CASES = [
    {
        "id": "printer_jam",
        "query": "打印机卡纸怎么办？",
        "expected_route": "rag",
        "expected_retrieval_terms": ["卡纸", "打印机", "取出"],
        "expected_answer_terms": ["关机", "轻轻取出", "硒鼓"],
        "expected_source_any": ["打印机常见故障 > 卡纸处理"],
    },
    {
        "id": "network_failure",
        "query": "网连不上了",
        "expected_route": "rag",
        "expected_retrieval_terms": ["网络", "连接", "失败"],
        "expected_answer_terms": ["检查", "网络"],
    },
    {
        "id": "error_code",
        "query": "E1005怎么处理",
        "expected_route": "rag",
        "expected_retrieval_terms": ["E1005", "错误"],
        "expected_answer_terms": ["E1005"],
    },
    {
        "id": "repair_report",
        "query": "我电脑坏了",
        "expected_route": "repair",
        "expected_retrieval_terms": [],
        "expected_answer_terms": [],
    },
    {
        "id": "unknown_query",
        "query": "今天天气怎么样",
        "expected_route": "unknown",
        "expected_retrieval_terms": [],
        "expected_answer_terms": [],
    },
]