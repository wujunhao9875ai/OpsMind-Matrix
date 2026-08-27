"""熔断器状态机 - CLOSED → OPEN → HALF_OPEN 三态"""

import time
import threading
from enum import Enum
from app.core.logger import setup_logger, log_event

logger = setup_logger("circuit_breaker")


class CircuitState(Enum):
    CLOSED = "closed"        # 正常通行
    OPEN = "open"            # 熔断，拒绝请求
    HALF_OPEN = "half_open"  # 半开，放行一个探测请求


class CircuitBreaker:
    """单个 Agent 的熔断器

    状态迁移:
      CLOSED ──连续失败 threshold 次──► OPEN
      OPEN   ──timeout 秒后────────► HALF_OPEN
      HALF_OPEN ──成功──────────────► CLOSED
      HALF_OPEN ──失败──────────────► OPEN
    """

    def __init__(self, name: str, failure_threshold: int = 3, timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.timeout = timeout          # 熔断持续时间（秒）
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self.last_state_change = time.time()
        self._lock = threading.Lock()

    def allow_request(self) -> bool:
        """判断是否允许请求通过"""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                elapsed = time.time() - self.last_state_change
                if elapsed >= self.timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.last_state_change = time.time()
                    log_event(logger, "circuit_half_open", agent=self.name,
                              elapsed_s=round(elapsed, 2))
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return True

            return False

    def record_success(self):
        """记录成功，半开状态恢复为关闭"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.last_state_change = time.time()
                log_event(logger, "circuit_closed", agent=self.name)
            elif self.state == CircuitState.CLOSED:
                self.failure_count = 0

    def record_failure(self):
        """记录失败"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
                log_event(logger, "circuit_reopened", agent=self.name,
                          failures=self.failure_count)
            elif self.state == CircuitState.CLOSED and self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                self.last_state_change = time.time()
                log_event(logger, "circuit_opened", agent=self.name,
                          failures=self.failure_count)

    def reset(self):
        """手动重置熔断器"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.last_failure_time = 0.0
            self.last_state_change = time.time()
            log_event(logger, "circuit_reset", agent=self.name)

    def get_state(self) -> dict:
        """获取当前状态快照"""
        with self._lock:
            return {
                "agent": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "last_failure_time": self.last_failure_time,
                "last_state_change": self.last_state_change,
            }


class CircuitBreakerRegistry:
    """全局熔断器注册表，管理所有 Agent 的熔断器"""

    def __init__(self):
        self._breakers: dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get(self, agent_name: str) -> CircuitBreaker:
        with self._lock:
            if agent_name not in self._breakers:
                self._breakers[agent_name] = CircuitBreaker(name=agent_name)
            return self._breakers[agent_name]

    def get_all_states(self) -> dict:
        """获取所有熔断器状态"""
        with self._lock:
            return {name: cb.get_state() for name, cb in self._breakers.items()}

    def reset_all(self):
        with self._lock:
            for cb in self._breakers.values():
                cb.reset()


# 全局单例
circuit_breaker_registry = CircuitBreakerRegistry()