"""会话管理 - 内存存储（开发模式）"""
import json

_sessions: dict[str, dict] = {}


async def get_session(session_id: str) -> dict:
    """获取会话数据。"""
    return _sessions.get(session_id, {"intent": None, "slots": {}, "history": [], "summary": ""})


async def save_session(session_id: str, data: dict):
    """保存会话数据。"""
    _sessions[session_id] = data


async def add_message(session_id: str, role: str, content: str):
    """添加消息到会话历史。"""
    session = await get_session(session_id)
    session["history"].append({"role": role, "content": content})
    if len(session["history"]) > 100:
        session["history"] = session["history"][-100:]
    await save_session(session_id, session)


async def get_slots(session_id: str) -> dict:
    session = await get_session(session_id)
    return session.get("slots", {})


async def update_slot(session_id: str, key: str, value: str):
    session = await get_session(session_id)
    session["slots"][key] = value
    await save_session(session_id, session)


async def get_summary(session_id: str) -> str:
    session = await get_session(session_id)
    return session.get("summary", "")


async def set_summary(session_id: str, summary: str):
    session = await get_session(session_id)
    session["summary"] = summary
    await save_session(session_id, session)


async def clear_session(session_id: str):
    _sessions.pop(session_id, None)


# Backward compatibility
class SessionManager:
    """SessionManager 兼容类。"""
    async def get_session(self, session_id: str) -> dict:
        return await get_session(session_id)

    async def update_session(self, session_id: str, data: dict):
        await save_session(session_id, data)

    async def add_message(self, session_id: str, role: str, content: str):
        await add_message(session_id, role, content)

    async def get_slots(self, session_id: str) -> dict:
        return await get_slots(session_id)

    async def update_slot(self, session_id: str, key: str, value: str):
        await update_slot(session_id, key, value)

    async def get_summary(self, session_id: str) -> str:
        return await get_summary(session_id)

    async def set_summary(self, session_id: str, summary: str):
        await set_summary(session_id, summary)

    async def clear_session(self, session_id: str):
        await clear_session(session_id)


session_manager = SessionManager()