"""Seed engineer profiles into dispatch-agent database."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from app.database import async_session, init_db
from app.models.engineer import EngineerProfile
from sqlalchemy import select


ENGINEERS = [
    {
        "user_id": "engineer1",
        "display_name": "张三",
        "skills": ["hardware", "network"],
        "skill_levels": {"hardware": 4, "network": 3},
        "status": "available",
        "location": "5楼",
    },
    {
        "user_id": "engineer2",
        "display_name": "李四",
        "skills": ["software", "network"],
        "skill_levels": {"software": 4, "network": 3},
        "status": "available",
        "location": "3楼",
    },
    {
        "user_id": "engineer3",
        "display_name": "王五",
        "skills": ["hardware", "software"],
        "skill_levels": {"hardware": 3, "software": 3},
        "status": "available",
        "location": "7楼",
    },
]


async def seed():
    await init_db()
    async with async_session() as db:
        for eng_data in ENGINEERS:
            # Check if already exists
            result = await db.execute(
                select(EngineerProfile).where(EngineerProfile.user_id == eng_data["user_id"])
            )
            existing = result.scalar_one_or_none()
            if existing:
                print(f"Engineer {eng_data['user_id']} ({eng_data['display_name']}) already exists, skipping")
                continue
            engineer = EngineerProfile(**eng_data)
            db.add(engineer)
            print(f"Created engineer: {eng_data['user_id']} ({eng_data['display_name']})")
        await db.commit()
    print("Seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())