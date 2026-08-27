"""Orchestrator 配置 - 所有敏感值从环境变量读取"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # 数据库
    database_url: str = "postgresql+asyncpg://orchestrator:orchestrator123@localhost:5437/orchestrator_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    redis_password: str = ""

    # Consul
    consul_url: str = "http://consul:8500"

    # JWT
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # SiliconFlow API
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "Qwen/Qwen2.5-7B-Instruct"

    # CORS
    cors_origins: str = "*"

    # Rate limit
    rate_limit_per_minute: int = 60

    # Harness 配置
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_timeout: int = 30      # 熔断持续时间（秒）
    mcp_max_retries: int = 3
    mcp_retry_backoff_base: float = 1.0    # 指数退避基数（秒）

    class Config:
        env_file = ".env"


settings = Settings()