from fastapi import APIRouter
from app.database import engine
from sqlalchemy import text

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check():
    """Health check endpoint - verifies database connectivity."""
    status = {
        "status": "healthy",
        "service": "data-platform-mcp",
        "version": "1.0.0",
        "checks": {},
    }

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
            await conn.commit()
        status["checks"]["database"] = "ok"
    except Exception as e:
        status["checks"]["database"] = f"error: {str(e)}"
        status["status"] = "degraded"

    return status