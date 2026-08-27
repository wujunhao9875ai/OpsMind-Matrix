import re
import uuid
import hashlib


def generate_parent_id(doc_title: str, section_title: str, index: int) -> str:
    raw = f"{doc_title}:{section_title}:{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def split_by_headings(text: str) -> list[dict]:
    """按 Markdown ## 标题切分文档，返回结构块列表。"""
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    result = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        title_match = re.match(r"^## (.+)", section)
        section_title = title_match.group(1).strip() if title_match else ""
        result.append({"title": section_title, "content": section})
    return result


def chunk_text(text: str, chunk_size: int = 260, overlap: int = 50) -> list[str]:
    """按字符数切分文本，带重叠。"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks


def process_document(doc_title: str, content: str, parent_size: int = 500, child_size: int = 260, overlap: int = 50) -> list[dict]:
    """结构感知切块 + Parent-Child 分块。返回 child chunks 和 parent chunks 列表。"""
    sections = split_by_headings(content)
    all_chunks = []

    for section in sections:
        parent_chunks = chunk_text(section["content"], parent_size, overlap)
        for pi, parent_text in enumerate(parent_chunks):
            parent_id = generate_parent_id(doc_title, section["title"], pi)
            child_chunks = chunk_text(parent_text, child_size, overlap)
            for ci, child_text in enumerate(child_chunks):
                chunk_id = str(uuid.uuid4())
                all_chunks.append({
                    "id": chunk_id,
                    "parent_id": parent_id,
                    "chunk_type": "child",
                    "chunk_index": pi * 1000 + ci,
                    "section_title": section["title"],
                    "content": child_text,
                    "parent_text": parent_text,
                })
            # 同时存储 parent chunk（用于 LLM 上下文）
            parent_chunk_id = str(uuid.uuid4())
            all_chunks.append({
                "id": parent_chunk_id,
                "parent_id": parent_id,
                "chunk_type": "parent",
                "chunk_index": pi,
                "section_title": section["title"],
                "content": parent_text,
                "parent_text": parent_text,
            })

    return all_chunks