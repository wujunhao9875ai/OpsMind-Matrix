from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://dataplatform:dataplatform123@localhost:5436/data_platform_db"
    redis_url: str = "redis://localhost:6379/0"
    minio_url: str = "http://minio:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    consul_url: str = "http://consul:8500"
    vllm_url: str = "http://vllm:8000"
    jwt_secret: str = "demo-secret-key"
    material_quality_threshold: int = 80
    material_batch_size: int = 100

    class Config:
        env_file = ".env"


settings = Settings()