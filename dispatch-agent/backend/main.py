from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.api.health import router as health_router
from mcp_server import register_mcp_tools, mcp, register_to_consul
import traceback

app = FastAPI(title="Dispatch Agent MCP Server", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)

# ---- MCP HTTP Routes ----


@app.post("/mcp/tools/{tool_name}")
async def invoke_mcp_tool(tool_name: str, request: Request):
    """Invoke an MCP tool via HTTP."""
    try:
        body = await request.json()
        from mcp_server import mcp as _mcp
        for tool in _mcp._tool_manager._tools.values():
            if tool.name == tool_name:
                result = await tool.fn(**body)
                if isinstance(result, dict):
                    return result
                return {"result": result}
        return JSONResponse(status_code=404, content={"error": f"Tool '{tool_name}' not found"})
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback.format_exc()})


@app.get("/mcp/tools")
async def list_mcp_tools():
    """List all MCP tools."""
    from mcp_server import mcp as _mcp
    tools = []
    for tool in _mcp._tool_manager._tools.values():
        tools.append({
            "name": tool.name,
            "description": tool.description,
        })
    return {"tools": tools}


@app.on_event("startup")
async def startup():
    from app.database import init_db
    await init_db()
    register_mcp_tools()
    try:
        await register_to_consul()
    except Exception as e:
        print(f"Warning: Consul registration failed: {e}")