"""Database setup - async PostgreSQL."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def init_db():
    """Create all tables on startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # 幂等迁移：为已存在的 tickets 表补充新增列（create_all 不会修改已有表）
        await _ensure_columns(conn)


async def _ensure_columns(conn):
    """为 tickets 表补充缺失的列，保证升级后新增字段可用。"""
    columns = {
        "location": "VARCHAR(500)",
        "contact": "VARCHAR(128)",
    }
    for name, ddl_type in columns.items():
        try:
            await conn.execute(text(f"ALTER TABLE tickets ADD COLUMN IF NOT EXISTS {name} {ddl_type}"))
        except Exception:
            # 列已存在或数据库不支持 IF NOT EXISTS，忽略
            pass


async def get_db() -> AsyncSession:
    """Dependency injection for FastAPI routes."""
    async with async_session() as session:
        yield session