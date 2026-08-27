from fastapi import APIRouter
from datetime import datetime, timezone
from app.config import settings

router = APIRouter()


@router.get("/health")
async def health_check():
    """健康检查 - 返回各组件状态"""
    checks = {}

    # Database check
    try:
        from app.database import get_db, release_db, fetchone, _db_type
        conn = await get_db()
        try:
            await fetchone(conn, "SELECT 1")
            checks["database"] = f"ok ({_db_type})"
        finally:
            await release_db(conn)
    except Exception as e:
        checks["database"] = f"error: {str(e)}"

    # Redis check
    try:
        import redis.asyncio as aioredis
        redis_kwargs = {"decode_responses": True}
        if settings.redis_password:
            redis_kwargs["password"] = settings.redis_password
        r = aioredis.from_url(settings.redis_url, **redis_kwargs)
        await r.ping()
        await r.close()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"unavailable: {str(e)}"

    all_ok = all(v == "ok" or v.startswith("ok (") for v in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "service": "orchestrator",
        "version": "1.0.0",
        "checks": checks,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }