"""Warehouse Agent MCP Server - FastAPI 入口"""
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.health import router as health_router
from app.api.ocr_api import router as ocr_router
from app.core.logger import setup_logging
from app.config import settings
from mcp_server import TOOL_HANDLERS, MCP_TOOLS, MCP_RESOURCES, call_tool, handle_resource_read
import httpx
import uuid
import json

_LOCAL_MODE = os.environ.get("LOCAL_MODE", "1") == "1"

setup_logging()

app = FastAPI(title="Warehouse Agent MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(ocr_router)


# ---- MCP API Routes ----

@app.get("/mcp/tools")
async def list_tools():
    """List all MCP tools."""
    return {"tools": MCP_TOOLS}

@app.get("/mcp/resources")
async def list_resources():
    """List all MCP resources."""
    return {"resources": MCP_RESOURCES}

@app.post("/mcp/tools/{tool_name}")
async def invoke_tool(tool_name: str, request: Request):
    """Invoke an MCP tool."""
    body = await request.json()
    result = await call_tool(tool_name, body)
    return JSONResponse(content=json.loads(result))

@app.get("/mcp/resources/{uri:path}")
async def read_resource(uri: str):
    """Read an MCP resource."""
    result = await handle_resource_read(uri)
    return JSONResponse(content=json.loads(result))


@app.on_event("startup")
async def startup_event():
    """启动时初始化数据库并注册到 Consul"""
    from app.database import init_db
    await init_db()
    # Register to Consul
    try:
        service_id = str(uuid.uuid4())
        address = "localhost" if _LOCAL_MODE else "warehouse-agent"
        async with httpx.AsyncClient() as client:
            await client.put(f"{settings.consul_url}/v1/agent/service/register", json={
                "ID": service_id,
                "Name": "warehouse-agent",
                "Address": address,
                "Port": 8000,
                "Tags": ["mcp", "warehouse", "v1.0.0"],
                "Check": {
                    "HTTP": f"http://{address}:8000/health",
                    "Interval": "10s",
                    "Timeout": "3s",
                },
            })
        print(f"Warehouse Agent registered to Consul (ID: {service_id})")
    except Exception as e:
        print(f"Warning: Consul registration failed: {e}")
    print("Warehouse Agent MCP Server started on port 8000")