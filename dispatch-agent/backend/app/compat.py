"""兼容模块 - 提供跨数据库的 UUID 和 JSON 类型"""
from sqlalchemy import String, JSON

# SQLAlchemy 2.0+ 通用 UUID 类型，兼容 SQLite 和 PostgreSQL
try:
    from sqlalchemy.types import Uuid as UUID
except ImportError:
    # Fallback: 使用 String(36) 存储 UUID
    def UUID(as_uuid=False):
        return String(36)

__all__ = ["UUID", "JSON"]