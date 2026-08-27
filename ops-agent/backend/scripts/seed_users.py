"""
数据库种子脚本：创建演示用户（bcrypt 哈希密码）。
首次运行：python -m scripts.seed_users
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import async_session
from app.models.user import User
from app.utils.password import hash_password
from sqlalchemy import select


DEMO_USERS = [
    {"username": "admin", "password": "Admin@2024Demo", "role": "admin"},
    {"username": "user1", "password": "User1@2024Demo", "role": "user"},
    {"username": "user2", "password": "User2@2024Demo", "role": "user"},
]


async def seed():
    async with async_session() as db:
        for u in DEMO_USERS:
            result = await db.execute(select(User).where(User.username == u["username"]))
            existing = result.scalar_one_or_none()
            if existing:
                print(f"跳过已存在的用户: {u['username']}")
                continue
            user = User(
                username=u["username"],
                password_hash=hash_password(u["password"]),
                role=u["role"],
            )
            db.add(user)
            print(f"创建用户: {u['username']} (角色: {u['role']})")
        await db.commit()
        print("种子数据初始化完成。")


if __name__ == "__main__":
    asyncio.run(seed())