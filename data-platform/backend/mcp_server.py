"""MCP Server - 注册 MCP 工具和资源，注册到 Consul 服务发现"""
import os
import httpx
from app.config import settings
from app.core.logger import setup_logger

logger = setup_logger("mcp_server")

_LOCAL_MODE = os.environ.get("LOCAL_MODE", "1") == "1"

# MCP Tool definitions
MCP_TOOLS = [
    {
        "name": "export_dataset",
        "description": "导出训练数据集，支持 qa/classification/ticket 类型，支持 jsonl/csv 格式",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dataset_type": {"type": "string", "enum": ["qa", "classification", "ticket"], "default": "qa"},
                "format": {"type": "string", "enum": ["jsonl", "csv"], "default": "jsonl"},
                "split": {"type": "string", "enum": ["train", "val", "test"], "default": "train"},
                "size": {"type": "integer", "default": 1000},
            },
        },
    },
    {
        "name": "query_analytics",
        "description": "查询分析指标，如工单数量、解决率、响应时间、满意度等",
        "inputSchema": {
            "type": "object",
            "properties": {
                "metric_name": {"type": "string", "description": "指标名称: ticket_count, resolution_rate, avg_response_time, satisfaction_score, active_engineers, pending_tickets"},
                "time_range": {"type": "string", "default": "today"},
                "group_by": {"type": "string"},
            },
            "required": ["metric_name"],
        },
    },
    {
        "name": "material_generate",
        "description": "从对话/知识库自动生成训练素材（QA对、变体、考题、负样本）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source_type": {"type": "string", "enum": ["conversations", "knowledge_base"], "default": "conversations"},
                "count": {"type": "integer", "default": 100},
                "quality_threshold": {"type": "integer", "default": 80},
            },
        },
    },
    {
        "name": "data_import",
        "description": "导入外部数据到平台，支持批量导入原始事件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "数据来源标识"},
                "data_type": {"type": "string", "enum": ["events", "conversations", "knowledge"], "default": "events"},
                "payload": {"type": "array", "description": "待导入的数据数组"},
            },
            "required": ["source", "payload"],
        },
    },
]

MCP_RESOURCES = [
    {
        "uri": "dataset://{dataset_id}",
        "name": "Dataset Resource",
        "description": "获取指定数据集的信息",
        "mimeType": "application/json",
    },
    {
        "uri": "analytics://{metric_name}",
        "name": "Analytics Resource",
        "description": "获取指定分析指标的最新值",
        "mimeType": "application/json",
    },
    {
        "uri": "material://{material_id}",
        "name": "Material Resource",
        "description": "获取指定素材的详细信息",
        "mimeType": "application/json",
    },
]


def register_mcp_tools():
    """Register MCP tools and resources (in-memory registry for now)."""
    logger.info(f"Registered {len(MCP_TOOLS)} MCP tools and {len(MCP_RESOURCES)} MCP resources")
    return MCP_TOOLS, MCP_RESOURCES


async def register_to_consul():
    """Register this MCP server instance to Consul service discovery."""
    service_id = "data-platform-mcp"
    service_name = "data-platform-mcp"
    address = "localhost" if _LOCAL_MODE else "data-platform"
    payload = {
        "ID": service_id,
        "Name": service_name,
        "Address": address,
        "Port": 8000,
        "Tags": ["mcp", "data-platform", "v1.0.0"],
        "Check": {
            "HTTP": f"http://{address}:8000/health",
            "Interval": "10s",
            "Timeout": "3s",
        },
    }
    async with httpx.AsyncClient() as client:
        resp = await client.put(
            f"{settings.consul_url}/v1/agent/service/register",
            json=payload,
        )
        resp.raise_for_status()
    logger.info(f"Registered to Consul: {service_id}")


async def deregister_from_consul():
    """Deregister from Consul on shutdown."""
    service_id = "data-platform-mcp"
    async with httpx.AsyncClient() as client:
        await client.put(f"{settings.consul_url}/v1/agent/service/deregister/{service_id}")
    logger.info(f"Deregistered from Consul: {service_id}")