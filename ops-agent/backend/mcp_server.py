"""MCP Server for Ops Agent - 智能运维客服

注册 MCP 工具:
  - rag_search: 知识库检索问答
  - intent_classify: 意图分类
  - prefill_ticket: 生成预填工单
  - chat_reply: 对话回复

注册 MCP 资源:
  - knowledge://{doc_id}: 知识库文档
  - conversation://{session_id}: 会话历史
"""
import json
import os
import uuid
from app.core.rag_engine import search_knowledge, generate_rag_answer
from app.core.intent_classifier import classify_intent
from app.core.ticket_generator import generate_pre_ticket
from app.config import settings
from app.core.logger import setup_logger, log_event

logger = setup_logger("mcp_server")
_LOCAL_MODE = os.environ.get("LOCAL_MODE", "1") == "1"


class _ToolInfo:
    """Simple tool wrapper to mimic FastMCP tool interface."""
    __slots__ = ("name", "description", "fn")

    def __init__(self, name: str, description: str, fn):
        self.name = name
        self.description = description
        self.fn = fn


class _ResourceInfo:
    """Simple resource wrapper to mimic FastMCP resource interface."""
    __slots__ = ("uri_template", "description", "fn")

    def __init__(self, uri_template: str, description: str, fn):
        self.uri_template = uri_template
        self.description = description
        self.fn = fn


class _ToolManager:
    """Simple tool manager to mimic FastMCP._tool_manager."""
    __slots__ = ("_tools",)

    def __init__(self):
        self._tools: dict[str, _ToolInfo] = {}


class _ResourceManager:
    """Simple resource manager to mimic FastMCP._resource_manager."""
    __slots__ = ("_resources",)

    def __init__(self):
        self._resources: dict[str, _ResourceInfo] = {}


class SimpleMCP:
    """A lightweight replacement for FastMCP that provides the same tool/resource
    registration interface used by the ops-agent."""

    def __init__(self, name: str):
        self.name = name
        self._tool_manager = _ToolManager()
        self._resource_manager = _ResourceManager()

    def tool(self, name: str = None, description: str = None):
        """Decorator to register a tool function."""
        def decorator(fn):
            tool_name = name or fn.__name__
            tool_desc = description or (fn.__doc__ or "").strip().split("\n")[0]
            self._tool_manager._tools[tool_name] = _ToolInfo(
                name=tool_name,
                description=tool_desc,
                fn=fn,
            )
            return fn
        return decorator

    def resource(self, uri_template: str, description: str = None):
        """Decorator to register a resource function."""
        def decorator(fn):
            resource_desc = description or (fn.__doc__ or "").strip().split("\n")[0]
            self._resource_manager._resources[uri_template] = _ResourceInfo(
                uri_template=uri_template,
                description=resource_desc,
                fn=fn,
            )
            return fn
        return decorator


mcp = SimpleMCP("ops-agent")


def register_mcp_tools():
    """Register all MCP tools and resources."""

    # ==================== Tools ====================

    @mcp.tool()
    async def rag_search(query: str, top_k: int = 5, history: list = None, **kwargs) -> dict:
        """搜索运维知识库，返回相关文档内容（供 orchestrator 组装上下文）

        仅做检索，不在此处生成最终 LLM 回答 —— 最终回答由 orchestrator 统一流式生成，
        避免对同一问题重复调用 LLM 拖慢整条链路。
        """
        context_docs = await search_knowledge(query, top_k=top_k)
        if not context_docs:
            return {
                "answer": "",
                "sources": [],
                "documents": [],
            }
        return {
            "answer": "",
            "sources": [doc.get("id", "") for doc in context_docs],
            "documents": [
                {
                    "id": doc.get("id", ""),
                    "title": doc.get("section_title", "") or doc.get("title", ""),
                    "content": doc.get("parent_text", "") or doc.get("content", ""),
                    "score": doc.get("score", 0),
                }
                for doc in context_docs
            ],
        }

    @mcp.tool()
    async def intent_classify(message: str) -> dict:
        """对用户消息进行意图分类（repair/consult/check_progress）"""
        intent = classify_intent(message)
        return {"intent": intent, "confidence": 0.95}

    @mcp.tool()
    async def prefill_ticket(conversation_text: str) -> dict:
        """从对话文本中提取工单信息，返回预填工单"""
        from app.database import async_session
        async with async_session() as db:
            pre_ticket = await generate_pre_ticket(conversation_text, db)
            return pre_ticket

    @mcp.tool()
    async def chat_reply(query: str = "", session_id: str = "", message: str = "", history: list = None, **kwargs) -> dict:
        """生成运维知识库 RAG 回答"""
        from app.database import async_session
        user_query = message or query
        context_docs = await search_knowledge(user_query)
        answer = generate_rag_answer(user_query, context_docs, history=history)
        return {
            "reply": answer,
            "sources": [doc.get("id", "") for doc in context_docs],
        }

    # ==================== Resources ====================

    @mcp.resource("knowledge://{doc_id}")
    async def get_knowledge_resource(doc_id: str) -> str:
        """获取知识库文档内容"""
        from app.database import async_session
        from sqlalchemy import select
        from app.models.knowledge import KnowledgeDoc
        async with async_session() as db:
            result = await db.execute(
                select(KnowledgeDoc).where(KnowledgeDoc.id == uuid.UUID(doc_id))
            )
            doc = result.scalar_one_or_none()
            if doc:
                return json.dumps({
                    "id": str(doc.id),
                    "title": doc.title,
                    "content": doc.content,
                    "source": doc.source,
                    "status": doc.status,
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                }, ensure_ascii=False)
            return json.dumps({"error": "Document not found"}, ensure_ascii=False)

    @mcp.resource("conversation://{session_id}")
    async def get_conversation_resource(session_id: str) -> str:
        """获取会话历史记录"""
        from app.database import async_session
        from sqlalchemy import select
        from app.models.conversation import Conversation
        from app.models.message import Message
        async with async_session() as db:
            conv_result = await db.execute(
                select(Conversation).where(Conversation.id == uuid.UUID(session_id))
            )
            conv = conv_result.scalar_one_or_none()
            if not conv:
                return json.dumps({"error": "Conversation not found"}, ensure_ascii=False)

            msg_result = await db.execute(
                select(Message).where(Message.conversation_id == uuid.UUID(session_id)).order_by(Message.created_at)
            )
            messages = msg_result.scalars().all()
            return json.dumps({
                "id": str(conv.id),
                "title": conv.title,
                "status": conv.status,
                "messages": [
                    {
                        "id": str(m.id),
                        "role": m.role,
                        "content": m.content,
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in messages
                ],
            }, ensure_ascii=False)

    logger.info("MCP tools and resources registered for ops-agent")


async def register_to_consul():
    """Register this MCP server with Consul for service discovery."""
    import httpx
    service_id = str(uuid.uuid4())
    address = "localhost" if _LOCAL_MODE else "ops-agent"
    payload = {
        "ID": service_id,
        "Name": "ops-agent",
        "Address": address,
        "Port": 8000,
        "Tags": ["mcp", "ops", "knowledge", "v1.0.0"],
        "Check": {
            "HTTP": f"http://{address}:8000/health",
            "Interval": "10s",
            "Timeout": "3s",
        },
    }
    async with httpx.AsyncClient() as client:
        await client.put(f"{settings.consul_url}/v1/agent/service/register", json=payload)
    logger.info(f"Registered ops-agent with Consul (ID: {service_id})")


def extract_trace_id(headers: dict) -> str | None:
    """从请求头中提取 traceId。"""
    return headers.get("x-trace-id") or headers.get("trace-id") or headers.get("traceid")