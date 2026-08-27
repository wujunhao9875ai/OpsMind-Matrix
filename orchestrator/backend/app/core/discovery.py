"""服务发现 - Consul 集成 + 静态配置降级"""

import os
import httpx
from typing import Optional
from app.config import settings
from app.core.instance_pool import InstancePool
from app.core.logger import setup_logger, log_event

logger = setup_logger("discovery")

# Instance pools for each agent
pools: dict[str, InstancePool] = {}

# LOCAL_MODE: 使用 localhost + 独立端口（不依赖 Docker 网络）
# 默认启用，Docker Compose 部署时通过环境变量 LOCAL_MODE=0 关闭
_LOCAL_MODE = os.environ.get("LOCAL_MODE", "1") == "1"

STATIC_AGENTS = {
    "ops-agent": [
        {
            "address": "localhost" if _LOCAL_MODE else "ops-agent",
            "port": 8011 if _LOCAL_MODE else 8000,
        }
    ],
    "dispatch-agent": [
        {
            "address": "localhost" if _LOCAL_MODE else "dispatch-agent",
            "port": 8012 if _LOCAL_MODE else 8000,
        }
    ],
    "warehouse-agent": [
        {
            "address": "localhost" if _LOCAL_MODE else "warehouse-agent",
            "port": 8013 if _LOCAL_MODE else 8000,
        }
    ],
    "data-platform": [
        {
            "address": "localhost" if _LOCAL_MODE else "data-platform",
            "port": 8014 if _LOCAL_MODE else 8000,
        }
    ],
}

# Agent 健康检查端点列表（按优先级尝试）
AGENT_HEALTH_ENDPOINTS = [
    "/health",
]


async def init_discovery():
    """Initialize service discovery. Try Consul first, fallback to static config."""
    for agent_name in STATIC_AGENTS:
        pools[agent_name] = InstancePool(agent_name)

    # Try Consul service discovery
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.consul_url}/v1/agent/services")
            if resp.status_code == 200:
                services = resp.json()
                for svc_id, svc in services.items():
                    agent_name = svc.get("Service")
                    if agent_name in pools:
                        pools[agent_name].add_instance({
                            "id": svc_id,
                            "address": svc.get("Address", agent_name),
                            "port": svc.get("Port", 8000),
                        })
                log_event(logger, "discovery_initialized", source="consul", agent_count=len(services))
                return
    except Exception as e:
        log_event(logger, "consul_unavailable", level="WARN", error=str(e))

    # Fallback to static config
    for agent_name, instances in STATIC_AGENTS.items():
        for inst in instances:
            pools[agent_name].add_instance({
                "id": f"{agent_name}-static",
                "address": inst["address"],
                "port": inst["port"],
            })
    log_event(logger, "discovery_initialized", source="static", agent_count=len(STATIC_AGENTS))


async def check_agent_health(agent_name: str) -> dict:
    """检查单个 Agent 的健康状态

    Returns:
        {"healthy": bool, "agent": str, "instance_id": str, "error": str|None}
    """
    pool = pools.get(agent_name)
    if not pool or pool.is_empty:
        return {"healthy": False, "agent": agent_name, "instance_id": None, "error": "no instances"}

    # 取第一个实例做健康探测
    instances = pool.get_all_instances()
    if not instances:
        return {"healthy": False, "agent": agent_name, "instance_id": None, "error": "no instances"}

    inst = instances[0]
    inst_id = inst.get("id", "unknown")
    address = inst.get("address", "localhost")
    port = inst.get("port", 8000)

    async with httpx.AsyncClient(timeout=2.0) as client:
        for endpoint in AGENT_HEALTH_ENDPOINTS:
            try:
                url = f"http://{address}:{port}{endpoint}"
                resp = await client.get(url)
                if resp.status_code < 500:
                    return {"healthy": True, "agent": agent_name, "instance_id": inst_id, "error": None}
            except Exception:
                continue

    return {"healthy": False, "agent": agent_name, "instance_id": inst_id,
            "error": "all health endpoints unreachable"}


async def batch_health_check() -> dict[str, dict]:
    """批量并行探测所有 Agent 的健康状态

    Returns:
        {agent_name: {"healthy": bool, "agent": str, "instance_id": str, "error": str|None}}
    """
    import asyncio
    results = {}

    tasks = [check_agent_health(name) for name in STATIC_AGENTS]
    agent_names = list(STATIC_AGENTS.keys())
    gathered = await asyncio.gather(*tasks, return_exceptions=True)

    for name, result in zip(agent_names, gathered):
        if isinstance(result, Exception):
            results[name] = {"healthy": False, "agent": name, "instance_id": None, "error": str(result)}
        else:
            results[name] = result

    return results


async def refresh_instance_pools(health_results: dict[str, dict]) -> dict[str, bool]:
    """根据健康检查结果刷新实例池：剔除不健康实例

    Returns:
        {agent_name: is_available}
    """
    available = {}
    for agent_name, result in health_results.items():
        pool = pools.get(agent_name)
        if not pool:
            available[agent_name] = False
            continue

        if result.get("healthy"):
            available[agent_name] = True
        else:
            # 移除不健康实例
            unhealthy_id = result.get("instance_id")
            if unhealthy_id:
                pool.remove_instance(unhealthy_id)
            available[agent_name] = not pool.is_empty

    log_event(logger, "instance_pools_refreshed",
              available=[k for k, v in available.items() if v],
              unhealthy=[k for k, v in available.items() if not v])
    return available


async def get_agent_instance(agent_name: str) -> Optional[dict]:
    """Get a healthy instance for the given agent."""
    pool = pools.get(agent_name)
    if not pool:
        return None
    return pool.get_instance()


def release_agent_instance(agent_name: str, instance_id: str):
    """释放 Agent 实例"""
    pool = pools.get(agent_name)
    if pool:
        pool.release_instance(instance_id)