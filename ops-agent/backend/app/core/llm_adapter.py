"""LLM 适配器，使用 httpx 直接调用硅基流动 API。"""
import httpx
from app.config import settings
from app.core.logger import setup_logger, log_event

logger = setup_logger("llm_adapter")


class LLMAdapter:
    """LLM 适配器，封装硅基流动 API 调用。"""

    def __init__(self):
        self.base_url = settings.siliconflow_base_url.rstrip("/")
        self.api_key = settings.siliconflow_api_key
        self._available = bool(self.api_key)

    def _headers(self) -> dict:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(self, messages: list[dict], temperature: float = 0.1, timeout: int = 60) -> str:
        """调用 LLM 聊天。"""
        if not self._available:
            log_event(logger, "llm_unavailable", level="WARN")
            return self._fallback_chat(messages)

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._headers(),
                    json={
                        "model": settings.llm_model,
                        "messages": messages,
                        "temperature": temperature,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            log_event(logger, "llm_call_error", level="ERROR", error=str(e))
            return self._fallback_chat(messages)

    def embed(self, texts: list[str]) -> list[list[float]]:
        """生成文本嵌入向量。"""
        if not self._available:
            log_event(logger, "embedding_unavailable", level="WARN")
            # Return zero vectors as fallback
            return [[0.0] * settings.embedding_dim for _ in texts]

        try:
            with httpx.Client(timeout=120) as client:
                response = client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._headers(),
                    json={
                        "model": settings.embedding_model,
                        "input": texts,
                    },
                )
                response.raise_for_status()
                data = response.json()
                return [d["embedding"] for d in data["data"]]
        except Exception as e:
            log_event(logger, "embedding_error", level="ERROR", error=str(e))
            return [[0.0] * settings.embedding_dim for _ in texts]

    def _fallback_chat(self, messages: list[dict]) -> str:
        """当 LLM 不可用时的降级回复。"""
        user_msg = messages[-1]["content"] if messages else ""
        # Simple keyword-based fallback
        keywords_map = {
            "卡纸": "打印机卡纸的常见排查步骤：\n1. 关闭打印机电源，确保安全\n2. 打开打印机盖板，检查纸张路径\n3. 轻轻拉出卡住的纸张，注意不要撕裂\n4. 检查进纸盘是否有异物\n5. 清理搓纸轮上的灰尘\n6. 重新装入纸张，确保纸张平整\n7. 开机测试打印\n\n如果问题仍然存在，可能是搓纸轮磨损或传感器故障，建议报修。",
            "打印": "打印问题的常见排查：\n1. 检查打印机是否开机并联机\n2. 确认打印队列中没有卡住的任务\n3. 检查墨盒/碳粉是否充足\n4. 重新安装打印机驱动\n5. 检查连接线或网络连接\n\n如果以上步骤无效，请联系运维团队进一步排查。",
            "网络": "网络问题排查步骤：\n1. 检查网线是否插好\n2. 重启路由器和交换机\n3. 使用 ipconfig 检查 IP 地址\n4. ping 网关测试连通性\n5. 检查 DNS 设置\n\n如需进一步帮助，请提供更多细节。",
            "蓝屏": "Windows 蓝屏故障排查：\n1. 记录蓝屏错误代码\n2. 重启电脑进入安全模式\n3. 检查最近安装的驱动或软件\n4. 运行系统文件检查：sfc /scannow\n5. 检查硬盘健康状态\n6. 更新驱动程序\n\n如果频繁蓝屏，可能是硬件故障，建议报修。",
            "密码": "密码相关问题：\n1. 确认是否开启了大写锁定\n2. 尝试使用密码重置功能\n3. 联系 IT 管理员重置密码\n4. 检查账户是否被锁定\n\n如需重置密码，请联系 IT 支持团队。",
        }
        for keyword, reply in keywords_map.items():
            if keyword in user_msg:
                return reply
        return "您好！我是运维助手。由于 LLM 服务暂未配置，我目前只能提供基础帮助。\n\n如果您需要报修设备故障，请告诉我具体的设备信息和故障现象，我可以帮您生成工单。\n\n常见问题类型：打印机故障、网络问题、电脑故障、账号问题等。"


llm_adapter = LLMAdapter()