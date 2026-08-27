"""JWT 认证与角色权限依赖注入"""
from fastapi import Request, HTTPException, Depends
import jwt
from app.config import settings


def get_token_from_request(request: Request) -> str:
    """从请求头中提取 Bearer token"""
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    return auth_header[7:]


def get_current_user(request: Request) -> dict:
    """验证 JWT token，返回当前用户信息"""
    token = get_token_from_request(request)
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        sub = payload.get("sub")
        role = payload.get("role", "user")
        if not sub:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return {"username": sub, "role": role}
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_role(*allowed_roles: str):
    """工厂函数：返回一个检查当前用户角色的依赖"""

    async def role_checker(request: Request) -> dict:
        user = get_current_user(request)
        if user["role"] not in allowed_roles:
            raise HTTPException(
                status_code=403,
                detail=f"Role '{user['role']}' not allowed. Required: {', '.join(allowed_roles)}",
            )
        return user

    return role_checker


# 便捷依赖：按角色分组
require_admin = require_role("admin")
require_engineer = require_role("engineer")
require_storekeeper = require_role("storekeeper")
require_admin_or_engineer = require_role("admin", "engineer")
require_any_authenticated = require_role("admin", "engineer", "storekeeper", "user")