from datetime import datetime, timezone
from fastapi import APIRouter
from app.database import engine
from app.config import settings
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
async def health_check():
    checks = {}

    # Database check
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Redis check
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        await r.ping()
        await r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {str(e)}"

    # PGVector check
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector'"))
            row = result.scalar_one_or_none()
            checks["pgvector"] = "ok" if row == "vector" else "error: pgvector extension not installed"
    except Exception as e:
        checks["pgvector"] = f"error: {str(e)}"

    all_ok = all(v == "ok" for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "service": "ops-agent",
        "version": "1.0.0",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }