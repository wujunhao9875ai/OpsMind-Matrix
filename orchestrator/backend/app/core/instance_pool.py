"""实例池 - 加权轮询负载均衡"""

import threading
from typing import Optional


class InstancePool:
    """加权轮询实例池

    权重 = 1 / (active_requests + 1)
    活跃请求越少，权重越高，越容易被选中。
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        self.instances: list[dict] = []
        self._lock = threading.Lock()

    def add_instance(self, instance: dict):
        """添加实例"""
        with self._lock:
            if instance not in self.instances:
                instance.setdefault("active_requests", 0)
                self.instances.append(instance)

    def remove_instance(self, instance_id: str):
        """移除实例"""
        with self._lock:
            self.instances = [i for i in self.instances if i.get("id") != instance_id]

    def remove_unhealthy(self, unhealthy_ids: set[str]):
        """批量移除不健康实例"""
        with self._lock:
            self.instances = [i for i in self.instances if i.get("id") not in unhealthy_ids]

    def get_instance(self) -> Optional[dict]:
        """加权轮询选择实例

        权重 = 1 / (active_requests + 1)，避免除零。
        """
        with self._lock:
            if not self.instances:
                return None

            weights = [1.0 / (inst.get("active_requests", 0) + 1) for inst in self.instances]
            total_weight = sum(weights)

            if total_weight == 0:
                return self.instances[0]

            import random
            r = random.random() * total_weight
            cumulative = 0.0
            selected = self.instances[0]
            for inst, w in zip(self.instances, weights):
                cumulative += w
                if r <= cumulative:
                    selected = inst
                    break

            selected["active_requests"] = selected.get("active_requests", 0) + 1
            return selected

    def release_instance(self, instance_id: str):
        """释放实例，减少活跃请求计数"""
        with self._lock:
            for inst in self.instances:
                if inst.get("id") == instance_id:
                    inst["active_requests"] = max(0, inst.get("active_requests", 1) - 1)
                    break

    def get_all_instances(self) -> list[dict]:
        """获取所有实例快照"""
        with self._lock:
            return [dict(inst) for inst in self.instances]

    @property
    def healthy_count(self) -> int:
        return len(self.instances)

    @property
    def is_empty(self) -> bool:
        return len(self.instances) == 0