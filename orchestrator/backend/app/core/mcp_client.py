"""MCP Client - 统一调用各 Agent 的 MCP Tools，支持重试 + 超时分级"""

import httpx
import asyncio
from typing import Optional
from app.core.discovery import get_agent_instance, release_agent_instance
from app.core.logger import setup_logger, log_event

logger = setup_logger("mcp_client")

# Agent 超时配置（秒）
AGENT_TIMEOUTS = {
    "ops-agent": 60.0,        # RAG 检索慢
    "dispatch-agent": 10.0,
    "warehouse-agent": 10.0,
    "data-platform": 15.0,
}
DEFAULT_TIMEOUT = 10.0

# 重试配置
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # 指数退避基数: 1s → 2s → 4s


class MCPClient:
    def __init__(self):
        pass

    async def call_tool(
        self,
        agent_name: str,
        tool_name: str,
        arguments: dict,
        trace_id: str = None,
        retries: int = MAX_RETRIES,
    ) -> dict:
        """调用 Agent 的 MCP Tool，支持指数退避重试和分级超时

        Args:
            agent_name: Agent 名称
            tool_name: 工具名称
            arguments: 工具参数
            trace_id: 追踪 ID
            retries: 最大重试次数

        Returns:
            {"result": ..., "error": str|None, "degraded": bool, "retries": int}
        """
        timeout = AGENT_TIMEOUTS.get(agent_name, DEFAULT_TIMEOUT)
        instance = None
        instance_id = None

        for attempt in range(retries + 1):
            instance = await get_agent_instance(agent_name)
            if not instance:
                return {
                    "error": f"Agent {agent_name} is not available",
                    "degraded": True,
                    "retries": attempt,
                }
            instance_id = instance.get("id")

            url = f"http://{instance['address']}:{instance['port']}/mcp/tools/{tool_name}"
            headers = {"Content-Type": "application/json"}
            if trace_id:
                headers["X-Trace-Id"] = trace_id

            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(url, json=arguments, headers=headers)
                    response.raise_for_status()
                    data = response.json()

                    # 释放实例
                    if instance_id:
                        release_agent_instance(agent_name, instance_id)

                    return {"result": data, "error": None, "degraded": False, "retries": attempt}

            except httpx.TimeoutException:
                log_event(logger, "mcp_timeout", level="WARN", trace_id=trace_id,
                          agent=agent_name, tool=tool_name, attempt=attempt + 1)
                if instance_id:
                    release_agent_instance(agent_name, instance_id)
                if attempt < retries:
                    backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
                    await asyncio.sleep(backoff)
                else:
                    return {
                        "error": f"Agent {agent_name} timed out after {retries + 1} attempts",
                        "degraded": True,
                        "retries": attempt + 1,
                    }

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                log_event(logger, "mcp_http_error", level="ERROR", trace_id=trace_id,
                          agent=agent_name, tool=tool_name, status=status_code,
                          attempt=attempt + 1)
                if instance_id:
                    release_agent_instance(agent_name, instance_id)
                # 4xx 错误不重试，5xx 错误重试
                if 400 <= status_code < 500:
                    return {
                        "error": f"Agent {agent_name} returned {status_code}",
                        "degraded": True,
                        "retries": attempt,
                    }
                if attempt < retries:
                    backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
                    await asyncio.sleep(backoff)
                else:
                    return {
                        "error": f"Agent {agent_name} returned {status_code} after {retries + 1} attempts",
                        "degraded": True,
                        "retries": attempt + 1,
                    }

            except Exception as e:
                log_event(logger, "mcp_error", level="ERROR", trace_id=trace_id,
                          agent=agent_name, tool=tool_name, error=str(e),
                          attempt=attempt + 1)
                if instance_id:
                    release_agent_instance(agent_name, instance_id)
                if attempt < retries:
                    backoff = RETRY_BACKOFF_BASE * (2 ** attempt)
                    await asyncio.sleep(backoff)
                else:
                    return {
                        "error": str(e),
                        "degraded": True,
                        "retries": attempt + 1,
                    }

        return {"error": "Unexpected retry loop exit", "degraded": True, "retries": retries}


mcp_client = MCPClient()