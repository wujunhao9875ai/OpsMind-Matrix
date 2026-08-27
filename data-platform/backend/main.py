from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.health import router as health_router
from app.api.export import router as export_router
from mcp_server import register_mcp_tools, register_to_consul, MCP_TOOLS
from app.config import settings
from app.core.analytics_engine import query_metrics
from app.core.dataset_builder import export_dataset
from app.core.material_factory import generate_materials
from app.core.data_collector import consume_events
import asyncio
import json

app = FastAPI(title="Data Platform MCP Server", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(health_router)
app.include_router(export_router)

# ---- MCP HTTP Routes ----

@app.get("/mcp/tools")
async def list_mcp_tools():
    return {"tools": MCP_TOOLS}

@app.post("/mcp/tools/{tool_name}")
async def invoke_mcp_tool(tool_name: str, request: Request):
    body = await request.json()
    
    if tool_name == "export_dataset":
        return await export_dataset(
            dataset_type=body.get("dataset_type", "qa"),
            format=body.get("format", "jsonl"),
            split=body.get("split", "train"),
            size=body.get("size", 1000),
        )
    elif tool_name == "query_analytics":
        return await query_metrics(
            metric_name=body.get("metric_name", "ticket_count"),
            time_range=body.get("time_range", "today"),
            group_by=body.get("group_by"),
        )
    elif tool_name == "material_generate":
        return await generate_materials(
            source_type=body.get("source_type", "conversations"),
            count=body.get("count", 100),
            quality_threshold=body.get("quality_threshold", 80),
        )
    elif tool_name == "data_import":
        return {"success": True, "imported": len(body.get("payload", []))}
    
    return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})

@app.on_event("startup")
async def startup():
    from app.database import init_db
    await init_db()
    register_mcp_tools()
    # 启动数据采集后台任务：从 Redis 消费各 Agent 上报的原始事件并入库
    asyncio.create_task(consume_events())
    try:
        await register_to_consul()
    except Exception as e:
        print(f"Warning: Consul registration failed: {e}")