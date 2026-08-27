import zipfile
import io
import hashlib
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Body
from sqlalchemy import select, delete
from app.database import async_session
from app.core.llm_adapter import llm_adapter

# Lazy bm25_retriever
try:
    from app.core.bm25_retriever import bm25_retriever
except ImportError:
    bm25_retriever = None
from app.utils.chunker import process_document
from app.models.knowledge import KnowledgeDoc, KnowledgeChunk
from app.config import settings

router = APIRouter()

MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB
MAX_ZIP_FILES = 50
MAX_ZIP_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50MB
ALLOWED_MIME_TYPES = {"text/markdown", "text/plain", "application/zip", "application/x-zip-compressed"}
ALLOWED_EXTENSIONS = {".md", ".txt", ".zip"}


def _content_hash(content: str) -> str:
    """计算内容 MD5 哈希，用于判断内容是否变化。"""
    return hashlib.md5(content.encode("utf-8")).hexdigest()


@router.post("/api/v1/knowledge/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
):
    """上传知识库文档（支持 .md 和 .zip）。

    热更新机制：按 source（文件名）去重，同文件名自动覆盖旧文档。
    内容哈希校验：内容未变时跳过索引，直接返回已有文档信息。
    """
    # 文件扩展名校验
    ext = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"不支持的文件类型: {ext}，仅支持 {', '.join(ALLOWED_EXTENSIONS)}")

    # MIME 类型校验（如果提供了 content_type）
    if file.content_type and file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=400, detail=f"不支持的 MIME 类型: {file.content_type}")

    content = await file.read()

    # 文件大小校验
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail=f"文件过大，最大支持 {MAX_UPLOAD_SIZE // 1024 // 1024}MB")

    if file.filename.endswith(".zip"):
        # 批量导入 zip 中的 Markdown 文件
        results = []
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            # ZIP 炸弹防护：检查解压后总大小
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > MAX_ZIP_UNCOMPRESSED_SIZE:
                raise HTTPException(status_code=400, detail=f"ZIP 解压后总大小超过限制 {MAX_ZIP_UNCOMPRESSED_SIZE // 1024 // 1024}MB")

            md_files = [name for name in zf.namelist() if name.endswith(".md") or name.endswith(".txt")]
            if len(md_files) > MAX_ZIP_FILES:
                raise HTTPException(status_code=400, detail=f"ZIP 内文件数超过限制 {MAX_ZIP_FILES}")

            for name in md_files:
                doc_content = zf.read(name).decode("utf-8")
                doc_title = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                results.append(await _upsert_document(doc_title, doc_content, name))
        return {"imported": len(results), "docs": results}
    else:
        content_str = content.decode("utf-8")
        doc_title = file.filename.rsplit(".", 1)[0]
        result = await _upsert_document(doc_title, content_str, file.filename)
        return {"imported": 1, "doc": result}


async def _upsert_document(title: str, content: str, source: str) -> dict:
    """上传文档（热更新）：按 source 去重，内容未变则跳过，变了则替换。"""
    new_hash = _content_hash(content)

    async with async_session() as db:
        # 查找是否已有同 source 的文档
        result = await db.execute(
            select(KnowledgeDoc).where(KnowledgeDoc.source == source)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # 内容哈希未变 → 跳过
            old_hash = getattr(existing, "content_hash", None)
            if old_hash == new_hash:
                return {
                    "id": str(existing.id), "title": title,
                    "chunk_count": existing.chunk_count, "status": existing.status,
                    "skipped": True, "reason": "内容未变化",
                }
            # 内容变了 → 先清理旧数据（向量随 chunk 删除一并清理）
            await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == existing.id))
            existing.title = title
            existing.content = content
            existing.status = "processing"
            existing.content_hash = new_hash
            doc = existing
        else:
            doc = KnowledgeDoc(title=title, content=content, source=source, status="processing")
            doc.content_hash = new_hash
            db.add(doc)

        await db.commit()
        await db.refresh(doc)

        # 索引文档
        await _index_document(db, doc)
        return {"id": str(doc.id), "title": title, "chunk_count": doc.chunk_count, "status": doc.status}


async def _index_document(db, doc: KnowledgeDoc) -> None:
    """对文档执行切块、向量化、存储。"""
    chunks = process_document(
        doc.title, doc.content,
        settings.parent_chunk_size, settings.child_chunk_size, settings.chunk_overlap,
    )

    # 向量化 child chunks
    child_chunks = [c for c in chunks if c["chunk_type"] == "child"]
    child_contents = [c["content"] for c in child_chunks]

    embeddings_map: dict[str, list[float]] = {}
    if child_contents:
        try:
            child_embeddings = llm_adapter.embed(child_contents)
            embeddings_map = {
                child_chunks[i]["id"]: child_embeddings[i]
                for i in range(len(child_chunks))
            }
        except Exception as e:
            doc.status = "archived"
            await db.commit()
            raise HTTPException(status_code=500, detail=f"向量化失败: {str(e)}")

    # 保存所有 chunks 到数据库（向量存于 KnowledgeChunk.embedding）
    for chunk in chunks:
        c = KnowledgeChunk(
            doc_id=doc.id,
            parent_id=chunk["parent_id"],
            chunk_type=chunk["chunk_type"],
            chunk_index=chunk["chunk_index"],
            section_title=chunk["section_title"],
            content=chunk["content"],
            parent_text=chunk["parent_text"],
            embedding=embeddings_map.get(chunk["id"]) if chunk["chunk_type"] == "child" else None,
        )
        db.add(c)

    doc.chunk_count = len(chunks)
    doc.status = "active"
    await db.commit()

    # 重建 BM25 索引
    await _rebuild_bm25_index()


@router.get("/api/v1/knowledge/docs")
async def list_docs(
    page: int = 1,
    page_size: int = 20,
):
    """分页获取知识库文档列表。"""
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    async with async_session() as db:
        # 总数
        count_result = await db.execute(select(KnowledgeDoc))
        total = len(count_result.scalars().all())

        # 分页查询
        result = await db.execute(
            select(KnowledgeDoc)
            .order_by(KnowledgeDoc.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        docs = result.scalars().all()
        items = [
            {
                "id": str(d.id),
                "title": d.title,
                "chunk_count": d.chunk_count,
                "source": d.source,
                "status": d.status,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
            for d in docs
        ]
        return {"total": total, "page": page, "page_size": page_size, "items": items}


@router.get("/api/v1/knowledge/docs/{doc_id}")
async def get_doc(doc_id: str):
    """获取单个知识库文档详情。"""
    async with async_session() as db:
        result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        return {
            "id": str(doc.id),
            "title": doc.title,
            "content": doc.content,
            "source": doc.source,
            "chunk_count": doc.chunk_count,
            "status": doc.status,
            "created_at": doc.created_at.isoformat() if doc.created_at else None,
            "updated_at": doc.updated_at.isoformat() if doc.updated_at else None,
        }


@router.put("/api/v1/knowledge/docs/{doc_id}")
async def update_doc(doc_id: str, content: str = Body(..., media_type="text/plain")):
    """更新文档内容并触发重索引（热更新）。

    请求体为纯文本/Markdown 内容。
    """
    async with async_session() as db:
        result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        new_hash = _content_hash(content)
        old_hash = getattr(doc, "content_hash", None)
        if old_hash == new_hash:
            return {
                "id": str(doc.id), "title": doc.title,
                "chunk_count": doc.chunk_count, "status": doc.status,
                "skipped": True, "reason": "内容未变化",
            }

        # 清理旧数据（向量随 chunk 删除一并清理）
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id))

        doc.content = content
        doc.content_hash = new_hash
        doc.status = "processing"
        await db.commit()
        await db.refresh(doc)

        # 重索引
        await _index_document(db, doc)
        return {
            "id": str(doc.id), "title": doc.title,
            "chunk_count": doc.chunk_count, "status": doc.status,
        }


@router.delete("/api/v1/knowledge/docs/{doc_id}")
async def delete_doc(doc_id: str):
    """删除文档（清理 PGVector 向量 + PostgreSQL chunks + BM25）。"""
    async with async_session() as db:
        result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        await db.delete(doc)
        await db.commit()
        # 重建 BM25（移除已删除文档的条目）
        await _rebuild_bm25_index()
        return {"deleted": True}


@router.post("/api/v1/knowledge/docs/{doc_id}/reindex")
async def reindex_doc(doc_id: str):
    """手动触发重索引（热更新已有文档）。"""
    async with async_session() as db:
        result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")

        # 清理旧数据（向量随 chunk 删除一并清理）
        await db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id))

        doc.status = "processing"
        await db.commit()
        await db.refresh(doc)

        # 重索引
        await _index_document(db, doc)
        return {
            "id": str(doc.id), "title": doc.title,
            "chunk_count": doc.chunk_count, "status": doc.status,
        }


async def _rebuild_bm25_index():
    """从数据库中读取所有 active 文档的 child chunks，重建 BM25 索引。"""
    if bm25_retriever is None:
        return
    async with async_session() as db:
        result = await db.execute(
            select(KnowledgeChunk)
            .join(KnowledgeDoc, KnowledgeChunk.doc_id == KnowledgeDoc.id)
            .where(KnowledgeDoc.status == "active", KnowledgeChunk.chunk_type == "child")
        )
        chunks = result.scalars().all()
        documents = [
            {"id": str(c.id), "content": c.content, "doc_id": str(c.doc_id), "parent_text": c.parent_text}
            for c in chunks
        ]
        if documents:
            bm25_retriever.build_index(documents)