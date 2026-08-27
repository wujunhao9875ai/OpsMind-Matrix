import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from app.config import settings
from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.auth import router as auth_router, LoginRequest, login as auth_login, register as auth_register
from app.api.tools import router as tools_router
from app.api.dispatch import router as dispatch_router
from app.api.warehouse import router as warehouse_router
from app.core.discovery import init_discovery
from app.core.tracer import generate_trace_id
from app.core.logger import setup_logger, log_event
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    await init_discovery()
    yield

app = FastAPI(
    title="运维 AI 平台 Orchestrator",
    description="Multi-Agent 智能运维协调器 - 统一入口，智能路由",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS - 从配置读取
cors_origins = [o.strip() for o in settings.cors_origins.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Trace-Id"],
)

# 速率限制
limiter = Limiter(key_func=get_remote_address, default_limits=[f"{settings.rate_limit_per_minute}/minute"])
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# 路由注册
app.include_router(health_router)
app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(tools_router)
app.include_router(dispatch_router)
app.include_router(warehouse_router)

# 向后兼容：旧版 /api/auth/login 和 /api/auth/register
from fastapi import APIRouter as _APIRouter
_compat_auth = _APIRouter(prefix="/api/auth")
_compat_auth.add_api_route("/login", auth_login, methods=["POST"])
_compat_auth.add_api_route("/register", auth_register, methods=["POST"])
app.include_router(_compat_auth)


@app.middleware("http")
async def trace_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id", generate_trace_id())
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response