from fastapi import APIRouter
from app.database import engine
from sqlalchemy import text

router = APIRouter()


@router.get("/health")
async def health_check():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()
        return {"status": "ok", "service": "warehouse-agent", "version": "1.0.0", "database": "connected"}
    except Exception as e:
        return {"status": "degraded", "service": "warehouse-agent", "version": "1.0.0", "database": str(e)}


@router.get("/api/v1/health")
async def health_check_v1():
    return {"status": "ok"}