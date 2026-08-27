"""数据库层 - PostgreSQL (asyncpg) + SQLite 回退"""
import logging
import os
from app.config import settings

logger = logging.getLogger("db")

# 连接池
_pool = None
_use_postgres = True
_db_type = "postgresql"


async def get_pool():
    """获取数据库连接池（懒加载）"""
    global _pool, _use_postgres, _db_type
    if _pool is not None:
        return _pool

    db_url = settings.database_url
    if db_url.startswith("postgresql"):
        try:
            import asyncpg
            _pool = await asyncpg.create_pool(
                dsn=db_url.replace("postgresql+asyncpg://", "postgresql://"),
                min_size=2,
                max_size=10,
            )
            _db_type = "postgresql"
            logger.info("Connected to PostgreSQL")
        except Exception as e:
            logger.warning(f"PostgreSQL unavailable ({e}), falling back to SQLite")
            _use_postgres = False
            await _init_sqlite()
    else:
        _use_postgres = False
        await _init_sqlite()

    return _pool


async def _init_sqlite():
    global _pool, _db_type
    import aiosqlite
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "sessions.db")
    _pool = await aiosqlite.connect(db_path)
    _pool.row_factory = aiosqlite.Row
    await _pool.execute("PRAGMA journal_mode=WAL")
    await _pool.execute("PRAGMA foreign_keys=ON")
    _db_type = "sqlite"
    logger.info("Connected to SQLite (fallback)")


async def get_db():
    """获取数据库连接"""
    pool = await get_pool()
    if _db_type == "postgresql":
        return await pool.acquire()
    return pool


async def release_db(conn):
    """释放数据库连接"""
    if _db_type == "postgresql":
        pool = await get_pool()
        await pool.release(conn)
    # SQLite connection is shared, don't close


async def close_db():
    """关闭数据库连接池"""
    global _pool
    if _pool is not None:
        if _db_type == "postgresql":
            await _pool.close()
        else:
            await _pool.close()
        _pool = None


# ==================== SQL 辅助函数 ====================

import re as _re

# SQLite → PostgreSQL 语法转换
_DATETIME_RE = _re.compile(r"datetime\('now'(?:,\s*'([^']*)')?\)")


def _translate_sql(query: str) -> str:
    """将 SQLite 特有语法转换为 PostgreSQL 兼容语法"""
    def _replace_datetime(m):
        modifier = m.group(1)
        if modifier:
            return f"NOW() + INTERVAL '{modifier}'"
        return "NOW()"
    return _DATETIME_RE.sub(_replace_datetime, query)


def sql_placeholder(idx: int) -> str:
    """根据数据库类型返回占位符"""
    return f"${idx}" if _db_type == "postgresql" else "?"


def make_placeholders(count: int) -> str:
    """生成占位符列表"""
    if _db_type == "postgresql":
        return ", ".join(f"${i}" for i in range(1, count + 1))
    return ", ".join("?" for _ in range(count))


def _pg_convert(query: str, args: tuple) -> tuple[str, tuple]:
    """PostgreSQL 模式：转换 ? 占位符 + 翻译 SQLite 语法"""
    # 先翻译 datetime('now', ...) → NOW() + INTERVAL ...
    query = _translate_sql(query)
    # 再转换 ? → $1, $2, ...
    idx = [0]
    def replacer(match):
        idx[0] += 1
        return f"${idx[0]}"
    query = _re.sub(r'\?', replacer, query)
    return query, args


async def execute(conn, query: str, *args):
    """执行 SQL，自动处理 PostgreSQL/SQLite 差异"""
    if _db_type == "postgresql":
        query, args = _pg_convert(query, args)
        return await conn.execute(query, *args)
    else:
        return await conn.execute(query, args)


async def fetchone(conn, query: str, *args):
    """查询单行"""
    if _db_type == "postgresql":
        query, args = _pg_convert(query, args)
        return await conn.fetchrow(query, *args)
    else:
        cursor = await conn.execute(query, args)
        return await cursor.fetchone()


async def fetchall(conn, query: str, *args):
    """查询多行"""
    if _db_type == "postgresql":
        query, args = _pg_convert(query, args)
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]
    else:
        cursor = await conn.execute(query, args)
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]


async def insert_and_get_id(conn, query: str, *args):
    """执行 INSERT 并返回新插入行的 id。

    PostgreSQL 使用 RETURNING id；SQLite 使用 lastrowid。
    """
    if _db_type == "postgresql":
        if "RETURNING" not in query.upper():
            query = query.rstrip().rstrip(";") + " RETURNING id"
        query, args = _pg_convert(query, args)
        row = await conn.fetchrow(query, *args)
        return row["id"] if row else None
    else:
        cursor = await conn.execute(query, args)
        return cursor.lastrowid


# ==================== 表初始化 ====================

async def init_db():
    """初始化数据库表"""
    pool = await get_pool()
    conn = await get_db()
    try:
        if _db_type == "postgresql":
            await _init_postgres_tables(conn)
        else:
            await _init_sqlite_tables(conn)
        await _migrate_feedback_columns(conn)
    finally:
        await release_db(conn)

    # 种子数据
    from app.api.auth import seed_default_users
    await seed_default_users()


async def _migrate_feedback_columns(conn):
    """为已存在的 messages 表补充 feedback / feedback_at 列（幂等）。"""
    try:
        if _db_type == "postgresql":
            await conn.execute(
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback VARCHAR(16) DEFAULT 'none'"
            )
            await conn.execute(
                "ALTER TABLE messages ADD COLUMN IF NOT EXISTS feedback_at TIMESTAMP"
            )
        else:
            cursor = await conn.execute("PRAGMA table_info(messages)")
            existing = {row[1] for row in await cursor.fetchall()}
            if "feedback" not in existing:
                await conn.execute("ALTER TABLE messages ADD COLUMN feedback TEXT DEFAULT 'none'")
            if "feedback_at" not in existing:
                await conn.execute("ALTER TABLE messages ADD COLUMN feedback_at TEXT")
            await conn.commit()
    except Exception as e:
        logger.warning(f"Feedback column migration skipped: {e}")


async def _init_postgres_tables(conn):
    await conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(64) UNIQUE NOT NULL,
            password_hash VARCHAR(256) NOT NULL,
            role VARCHAR(32) NOT NULL DEFAULT 'user',
            display_name VARCHAR(64) DEFAULT '',
            email VARCHAR(128) DEFAULT '',
            is_active BOOLEAN DEFAULT TRUE,
            login_attempts INTEGER DEFAULT 0,
            locked_until TIMESTAMP,
            last_login TIMESTAMP,
            last_login_attempt TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id VARCHAR(64) PRIMARY KEY,
            username VARCHAR(64) NOT NULL,
            title VARCHAR(256) DEFAULT '新对话',
            summary TEXT DEFAULT '',
            message_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS messages (
            id SERIAL PRIMARY KEY,
            session_id VARCHAR(64) NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
            role VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            msg_type VARCHAR(16) DEFAULT 'text',
            sources TEXT DEFAULT '[]',
            feedback VARCHAR(16) DEFAULT 'none',
            feedback_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id SERIAL PRIMARY KEY,
            username VARCHAR(64),
            action VARCHAR(64) NOT NULL,
            resource_type VARCHAR(32),
            resource_id VARCHAR(64),
            detail TEXT DEFAULT '',
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT NOW()
        );

        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username);
        CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_username ON audit_log(username);
        CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
    """)


async def _init_sqlite_tables(conn):
    await conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            display_name TEXT DEFAULT '',
            email TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            login_attempts INTEGER DEFAULT 0,
            locked_until TEXT,
            last_login TEXT,
            last_login_attempt TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sessions (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL,
            title TEXT DEFAULT '新对话',
            summary TEXT DEFAULT '',
            message_count INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
            content TEXT NOT NULL,
            msg_type TEXT DEFAULT 'text',
            sources TEXT DEFAULT '[]',
            feedback TEXT DEFAULT 'none',
            feedback_at TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            action TEXT NOT NULL,
            resource_type TEXT,
            resource_id TEXT,
            detail TEXT DEFAULT '',
            ip_address TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_sessions_username ON sessions(username);
        CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
        CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
        CREATE INDEX IF NOT EXISTS idx_audit_log_username ON audit_log(username);
        CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at DESC);
    """)
    await conn.commit()