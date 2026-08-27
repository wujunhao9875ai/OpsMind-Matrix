"""认证 API - 数据库用户管理 + bcrypt"""
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from app.config import settings
from app.database import get_db, release_db, execute, fetchone
from app.api.deps import require_admin, require_any_authenticated
import jwt
import bcrypt
import logging

logger = logging.getLogger("auth")
router = APIRouter(prefix="/api/v1/auth")


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str = Field(default="", max_length=64)


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(..., min_length=6, max_length=128)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


@router.post("/login")
async def login(request: LoginRequest):
    """用户登录"""
    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT id, username, password_hash, role, display_name, is_active, login_attempts, locked_until "
            "FROM users WHERE username = ?",
            request.username,
        )
    finally:
        await release_db(conn)

    if not row:
        # 恒定时间比较防止用户名枚举
        bcrypt.checkpw(b"dummy", bcrypt.hashpw(b"dummy", bcrypt.gensalt()))
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    user = dict(row) if isinstance(row, dict) else dict(row)

    # 检查账户锁定
    if user.get("locked_until"):
        from datetime import datetime
        locked_until = datetime.fromisoformat(user["locked_until"])
        if locked_until > datetime.utcnow():
            raise HTTPException(status_code=423, detail="账户已锁定，请稍后重试")

    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="账户已被禁用")

    # 验证密码
    if not verify_password(request.password, user["password_hash"]):
        # 记录失败次数
        await _record_login_failure(request.username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 登录成功，重置失败计数
    await _reset_login_attempts(request.username)

    token = jwt.encode(
        {"sub": request.username, "role": user["role"], "user_id": user["id"]},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )
    logger.info(f"User {request.username} logged in successfully")
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "username": request.username,
        "display_name": user.get("display_name", ""),
    }


@router.post("/register")
async def register(request: RegisterRequest):
    """用户注册（管理员可关闭）"""
    conn = await get_db()
    try:
        existing = await fetchone(conn,
            "SELECT id FROM users WHERE username = ?", request.username,
        )
        if existing:
            raise HTTPException(status_code=409, detail="用户名已存在")

        password_hash = hash_password(request.password)
        await execute(conn,
            "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)",
            request.username, password_hash, "user", request.display_name or request.username,
        )
    finally:
        await release_db(conn)

    logger.info(f"New user registered: {request.username}")
    return {"status": "ok", "message": "注册成功，请登录"}


# ==================== 管理员用户管理 ====================

@router.get("/users")
async def list_users(user: dict = Depends(require_admin)):
    """获取用户列表 - 仅管理员"""
    conn = await get_db()
    try:
        from app.database import fetchall
        users = await fetchall(conn,
            "SELECT id, username, role, display_name, email, is_active, "
            "login_attempts, last_login, created_at FROM users ORDER BY id"
        )
        return {"users": users}
    finally:
        await release_db(conn)


@router.put("/users/{username}/role")
async def change_user_role(username: str, request: Request, user: dict = Depends(require_admin)):
    """修改用户角色 - 仅管理员"""
    body = await request.json()
    new_role = body.get("role")
    if new_role not in ("admin", "engineer", "storekeeper", "user"):
        raise HTTPException(status_code=400, detail="无效的角色")
    conn = await get_db()
    try:
        await execute(conn,
            "UPDATE users SET role = ?, updated_at = datetime('now') WHERE username = ?",
            new_role, username,
        )
    finally:
        await release_db(conn)
    logger.info(f"Admin {user['username']} changed {username}'s role to {new_role}")
    return {"status": "ok"}


@router.put("/users/{username}/status")
async def toggle_user_status(username: str, request: Request, user: dict = Depends(require_admin)):
    """启用/禁用用户 - 仅管理员"""
    body = await request.json()
    is_active = body.get("is_active", True)
    conn = await get_db()
    try:
        await execute(conn,
            "UPDATE users SET is_active = ?, updated_at = datetime('now') WHERE username = ?",
            1 if is_active else 0, username,
        )
    finally:
        await release_db(conn)
    logger.info(f"Admin {user['username']} set {username} active={is_active}")
    return {"status": "ok"}


# ==================== 内部辅助函数 ====================

async def _record_login_failure(username: str):
    conn = await get_db()
    try:
        await execute(conn,
            "UPDATE users SET login_attempts = login_attempts + 1, "
            "last_login_attempt = datetime('now') WHERE username = ?",
            username,
        )
        # 5次失败锁定30分钟
        await execute(conn,
            "UPDATE users SET locked_until = datetime('now', '+30 minutes') "
            "WHERE username = ? AND login_attempts >= 5",
            username,
        )
    finally:
        await release_db(conn)


async def _reset_login_attempts(username: str):
    conn = await get_db()
    try:
        await execute(conn,
            "UPDATE users SET login_attempts = 0, locked_until = NULL, "
            "last_login = datetime('now') WHERE username = ?",
            username,
        )
    finally:
        await release_db(conn)


# ==================== 种子数据 ====================

async def seed_default_users():
    """初始化默认用户（仅首次运行）"""
    conn = await get_db()
    try:
        row = await fetchone(conn, "SELECT COUNT(*) as cnt FROM users")
        if row:
            cnt = row["cnt"] if isinstance(row, dict) else row[0] if hasattr(row, '__getitem__') else 0
            if cnt > 0:
                return

        default_users = [
            ("admin", "Admin@2024Demo", "admin", "管理员"),
            ("engineer1", "Engineer@123", "engineer", "张三"),
            ("engineer2", "Engineer@123", "engineer", "李四"),
            ("engineer3", "Engineer@123", "engineer", "王五"),
            ("storekeeper", "storekeeper123", "storekeeper", "库管员"),
            ("testuser", "User@123", "user", "测试用户"),
        ]
        for username, password, role, display_name in default_users:
            password_hash = hash_password(password)
            await execute(conn,
                "INSERT INTO users (username, password_hash, role, display_name) VALUES (?, ?, ?, ?)",
                username, password_hash, role, display_name,
            )
        logger.info("Default users seeded successfully")
    finally:
        await release_db(conn)