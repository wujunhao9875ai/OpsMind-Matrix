import re

# 关键实体提取正则：错误码、型号、版本号
ENTITY_PATTERNS = [
    r"[A-Z]{1,5}\d{2,6}",    # 错误码: E1005, ANP220
    r"[A-Z]{2,5}-\d{2,4}",   # 型号: ANP-220-CN
    r"v\d+\.\d+(\.\d+)?",    # 版本号: v1.5, v2.0.1
]


def extract_entities(text: str) -> set[str]:
    """从文本中提取关键实体（错误码、型号、版本号）。"""
    entities = set()
    for pattern in ENTITY_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        entities.update(matches)
    return entities


def check_coverage(user_query: str, llm_answer: str, source_docs: list[dict]) -> str:
    """检查回答是否覆盖了用户问题中的关键实体，缺失则从来源补充。"""
    query_entities = extract_entities(user_query)
    if not query_entities:
        return llm_answer

    answer_lower = llm_answer.lower()
    missing = [e for e in query_entities if e.lower() not in answer_lower]

    if not missing:
        return llm_answer

    # 从来源文档中查找缺失实体的信息
    supplements = []
    for entity in missing:
        for doc in source_docs:
            parent_text = doc.get("parent_text", "")
            if entity.lower() in parent_text.lower():
                lines = [l.strip() for l in parent_text.split("\n") if entity.lower() in l.lower()]
                if lines:
                    section = doc.get("section_title", "未知")
                    supplements.append(f"{entity} 的相关信息：{lines[0][:200]}（来源：{section}）")
                    break

    if supplements:
        return llm_answer + "\n\n---\n补充信息：\n" + "\n".join(supplements)

    return llm_answer


def validate_citations(answer: str, valid_section_titles: list[str]) -> dict:
    """校验回答中引用的来源是否合法（section_title 级别）。"""
    cited = re.findall(r"\[来源: ([^\]]+)\]", answer)
    invalid = [c for c in cited if c not in valid_section_titles]
    return {
        "verified": len(invalid) == 0,
        "answer_sources": cited,
        "invalid_sources": invalid,
    }