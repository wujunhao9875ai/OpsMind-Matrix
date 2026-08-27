from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://warehouse:warehouse123@localhost:5435/warehouse_db"
    redis_url: str = "redis://localhost:6379/0"
    paddleocr_url: str = "http://paddleocr:8866"
    consul_url: str = "http://consul:8500"
    jwt_secret: str = "demo-secret-key"
    jwt_algorithm: str = "HS256"
    low_stock_threshold: int = 5
    idle_device_days: int = 90

    # SiliconFlow API (硅基流动)
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "Qwen/Qwen3-32B"
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"

    class Config:
        env_file = ".env"


settings = Settings()