from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://opsagent:opsagent123@localhost:5434/ops_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # vLLM
    vllm_url: str = "http://vllm:8000"

    # Consul
    consul_url: str = "http://consul:8500"

    # SiliconFlow API (硅基流动)
    siliconflow_api_key: str = ""
    siliconflow_base_url: str = "https://api.siliconflow.cn/v1"
    llm_model: str = "Qwen/Qwen3-32B"
    embedding_model: str = "Qwen/Qwen3-Embedding-8B"
    reranker_model: str = "Qwen/Qwen3-Reranker-8B"

    # Vector
    embedding_dim: int = 4096

    # Auth
    jwt_secret: str = "demo-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Rate Limit
    rate_limit_per_minute: int = 60

    # RAG
    retrieval_top_k: int = 5
    dense_k: int = 10
    sparse_k: int = 10
    similarity_threshold: float = 0.4
    max_recent_messages: int = 6
    parent_chunk_size: int = 500
    child_chunk_size: int = 260
    chunk_overlap: int = 50

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()