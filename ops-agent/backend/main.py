import app.compat  # noqa: F401 - must be first for langchain compat
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.health import router as health_router
from app.api.knowledge import router as knowledge_router
from app.config import settings
from mcp_server import register_mcp_tools, mcp, register_to_consul
import time
import traceback

app = FastAPI(title="Ops Agent MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 简易速率限制中间件
_rate_limit_store: dict[str, list[float]] = {}
_last_cleanup = time.time()
CLEANUP_INTERVAL = 300  # 每 5 分钟清理一次过期 key


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    global _last_cleanup
    client_ip = request.client.host if request.client else "unknown"
    now = time.time()
    window = 60  # 60 秒窗口

    # 定期清理过期的 IP key
    if now - _last_cleanup > CLEANUP_INTERVAL:
        _last_cleanup = now
        expired_ips = [ip for ip, timestamps in _rate_limit_store.items() if not timestamps or all(now - t >= window for t in timestamps)]
        for ip in expired_ips:
            del _rate_limit_store[ip]

    if client_ip not in _rate_limit_store:
        _rate_limit_store[client_ip] = []

    # 清理过期记录
    _rate_limit_store[client_ip] = [t for t in _rate_limit_store[client_ip] if now - t < window]

    if len(_rate_limit_store[client_ip]) >= settings.rate_limit_per_minute:
        return JSONResponse(status_code=429, content={"detail": "请求过于频繁，请稍后再试"})

    _rate_limit_store[client_ip].append(now)
    response = await call_next(request)
    return response


app.include_router(health_router)
app.include_router(knowledge_router)

# ---- MCP HTTP Routes ----

@app.get("/mcp/tools")
async def list_mcp_tools():
    """List all MCP tools."""
    tools = []
    for tool in mcp._tool_manager._tools.values():
        tools.append({
            "name": tool.name,
            "description": tool.description,
        })
    return {"tools": tools}


@app.post("/mcp/tools/{tool_name}")
async def invoke_mcp_tool(tool_name: str, request: Request):
    """Invoke an MCP tool via HTTP."""
    try:
        body = await request.json()
        for tool in mcp._tool_manager._tools.values():
            if tool.name == tool_name:
                result = await tool.fn(**body)
                if isinstance(result, dict):
                    return result
                return {"result": result}
        return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback.format_exc()})


@app.on_event("startup")
async def startup_event():
    """启动时注册 MCP 工具、注册到 Consul 并重建 BM25 索引。"""
    # 初始化数据库
    from app.database import init_db
    await init_db()

    # 注册 MCP 工具
    register_mcp_tools()

    # 注册到 Consul（服务发现）
    try:
        await register_to_consul()
    except Exception as e:
        print(f"Warning: Consul registration failed: {e}")

    # 重建 BM25 索引（内存数据在容器重启后丢失）
    from app.api.knowledge import _rebuild_bm25_index
    try:
        await _rebuild_bm25_index()
        print("BM25 index rebuilt on startup")
    except Exception as e:
        print(f"Warning: BM25 index rebuild failed on startup: {e}")