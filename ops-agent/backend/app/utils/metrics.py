async def calculate_mrr(bad_cases: list[dict], search_fn) -> float:
    """计算 MRR（Mean Reciprocal Rank）。"""
    reciprocal_ranks = []
    for case in bad_cases:
        results = await search_fn(case["query"])
        found = False
        for rank, doc in enumerate(results, 1):
            if any(term in doc.get("content", "") for term in case.get("expected_retrieval_terms", [])):
                reciprocal_ranks.append(1.0 / rank)
                found = True
                break
        if not found:
            reciprocal_ranks.append(0.0)
    return sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0


def calculate_hallucination_rate(citation_results: list[dict]) -> float:
    """计算幻觉率。"""
    if not citation_results:
        return 0.0
    unverified = sum(1 for r in citation_results if not r.get("verified", False))
    return unverified / len(citation_results)


def calculate_rejection_rate(total_queries: int, rejected_queries: int) -> float:
    """计算拒答率。"""
    if total_queries == 0:
        return 0.0
    return rejected_queries / total_queries