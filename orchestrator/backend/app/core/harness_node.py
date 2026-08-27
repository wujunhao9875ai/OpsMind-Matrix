"""Harness 节点 - preflight 前置检查 + postflight 后置检查 + Agent 调用装饰器"""

import time
import asyncio
from app.core.discovery import batch_health_check, refresh_instance_pools, pools as discovery_pools
from app.core.circuit_breaker import circuit_breaker_registry
from app.core.mcp_client import mcp_client, AGENT_TIMEOUTS
from app.core.logger import setup_logger, log_event

logger = setup_logger("harness")


# ==================== preflight ====================

async def harness_preflight(state: dict) -> dict:
    """全局前置检查节点

    1. 检查 Redis 连接
    2. 检查 Consul 连接（已有服务发现兜底，不阻塞）
    3. 批量探测所有 Agent 健康状态
    4. 更新实例池，剔除不健康实例
    5. 输出可用 Agent 清单
    """
    start_time = time.time()
    preflight_info = {
        "redis_ok": True,
        "consul_ok": True,
        "health_results": {},
        "available_agents": [],
        "unavailable_agents": [],
    }

    # 1. 检查 Redis 连接
    try:
        from app.core.session import _get_redis
        redis = _get_redis()
        if redis is not None:
            await redis.ping()
        else:
            preflight_info["redis_ok"] = False
    except Exception as e:
        preflight_info["redis_ok"] = False
        log_event(logger, "preflight_redis_fail", level="WARN", error=str(e))

    # 2. Consul 检查（非阻塞，服务发现已有静态降级）
    # 跳过，init_discovery 已处理

    # 3. 批量探测 Agent 健康状态
    health_results = await batch_health_check()
    preflight_info["health_results"] = health_results

    # 4. 刷新实例池
    available = await refresh_instance_pools(health_results)
    preflight_info["available_agents"] = [k for k, v in available.items() if v]
    preflight_info["unavailable_agents"] = [k for k, v in available.items() if not v]

    # 5. 判断是否全部不可用
    all_degraded = len(preflight_info["available_agents"]) == 0

    preflight_info["duration_ms"] = round((time.time() - start_time) * 1000, 2)

    log_event(logger, "preflight_complete",
              available=preflight_info["available_agents"],
              unavailable=preflight_info["unavailable_agents"],
              all_degraded=all_degraded,
              duration_ms=preflight_info["duration_ms"])

    return {
        **state,
        "preflight": preflight_info,
        "all_degraded": all_degraded,
        "node_timings": {},
    }


# ==================== postflight ====================

async def harness_postflight(state: dict) -> dict:
    """全局后置检查节点

    1. 记录全链路耗时
    2. 记录成功/失败/降级次数
    3. 更新熔断器状态
    4. 输出 traceId + 全链路日志
    5. 上报指标
    """
    trace_id = state.get("trace_id", "unknown")
    node_timings = state.get("node_timings", {})
    degraded_agents = state.get("degraded_agents", [])
    agent_results = state.get("agent_results", {})

    # 统计数据
    success_count = 0
    failure_count = 0
    degraded_count = 0

    for agent_name, result in agent_results.items():
        if result.get("error"):
            if result.get("degraded"):
                degraded_count += 1
            else:
                failure_count += 1
        else:
            success_count += 1

    # 加上被跳过的降级 agent
    degraded_count += len(degraded_agents)

    # 获取熔断器状态
    cb_states = circuit_breaker_registry.get_all_states()

    # 全链路耗时
    total_duration_ms = state.get("total_duration_ms", 0)

    postflight_info = {
        "trace_id": trace_id,
        "total_duration_ms": total_duration_ms,
        "node_timings": node_timings,
        "success_count": success_count,
        "failure_count": failure_count,
        "degraded_count": degraded_count,
        "circuit_breaker_states": cb_states,
        "degraded_agents": degraded_agents,
    }

    log_event(logger, "postflight_complete",
              trace_id=trace_id,
              success=success_count,
              failure=failure_count,
              degraded=degraded_count,
              total_ms=total_duration_ms,
              cb_states={k: v["state"] for k, v in cb_states.items()})

    return {
        **state,
        "postflight": postflight_info,
    }


# ==================== Agent 调用 Harness 装饰器 ====================

async def call_agent_with_harness(
    agent_name: str,
    tool_name: str,
    arguments: dict,
    trace_id: str,
) -> dict:
    """带 Harness 的 Agent 调用

    内置: 熔断检查 → 健康检查 → 负载均衡 → 调用+重试 → 超时 → 熔断更新

    Returns:
        {"result": dict|None, "error": str|None, "degraded": bool, "degraded_reason": str}
    """
    # 1. 熔断检查
    breaker = circuit_breaker_registry.get(agent_name)
    if not breaker.allow_request():
        log_event(logger, "agent_blocked_circuit_open", trace_id=trace_id, agent=agent_name)
        return {
            "result": None,
            "error": f"Agent {agent_name} is circuit-broken",
            "degraded": True,
            "degraded_reason": "circuit_open",
        }

    # 2. 检查实例池是否为空
    pool = discovery_pools.get(agent_name)
    if not pool or pool.is_empty:
        return {
            "result": None,
            "error": f"Agent {agent_name} has no available instances",
            "degraded": True,
            "degraded_reason": "instance_pool_empty",
        }

    # 3. 调用 + 重试 + 超时（mcp_client 内部处理）
    call_result = await mcp_client.call_tool(agent_name, tool_name, arguments, trace_id)

    # 4. 更新熔断器状态
    if call_result.get("degraded"):
        breaker.record_failure()
        return {
            "result": call_result.get("result"),
            "error": call_result.get("error"),
            "degraded": True,
            "degraded_reason": "call_failed",
            "retries": call_result.get("retries", 0),
        }
    else:
        breaker.record_success()
        return {
            "result": call_result.get("result"),
            "error": None,
            "degraded": False,
            "degraded_reason": None,
            "retries": call_result.get("retries", 0),
        }


# ==================== 降级处理 ====================

def is_degraded_response(result: dict) -> bool:
    """判断 Agent 返回是否为'我处理不了'"""
    if not result or not result.get("result"):
        return False
    data = result["result"]
    reply = data.get("reply", "") or data.get("answer", "") or ""
    cant_handle_markers = ["我处理不了", "无法处理", "不在我的能力范围", "请换个方式", "我不理解"]
    for marker in cant_handle_markers:
        if marker in str(reply):
            return True
    return False