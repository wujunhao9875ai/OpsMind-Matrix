from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://dispatch:dispatch123@localhost:5432/dispatch_db"
    redis_url: str = "redis://localhost:6379/0"
    consul_url: str = "http://consul:8500"
    jwt_secret: str = "demo-secret-key"
    jwt_algorithm: str = "HS256"
    dispatch_skill_weight: float = 0.40
    dispatch_load_weight: float = 0.30
    dispatch_balance_weight: float = 0.20
    dispatch_performance_weight: float = 0.10
    dispatch_location_weight: float = 0.0
    sla_critical_minutes: int = 120
    sla_high_minutes: int = 240
    sla_medium_minutes: int = 480
    sla_low_minutes: int = 1440
    urge_cooldown_minutes: int = 30
    auto_close_days: int = 3
    unassigned_alert_minutes: int = 5

    class Config:
        env_file = ".env"


settings = Settings()