"""会话管理 - PostgreSQL 持久化 + Redis 缓存 + LLM 摘要压缩"""
import json
import logging
from datetime import datetime
from app.config import settings
from app.database import get_db, release_db, execute, fetchone, fetchall, insert_and_get_id

logger = logging.getLogger("session")

# Redis client (lazy init)
_redis = None
_redis_available = True

# 常量
MAX_RECENT_MESSAGES = 20
SUMMARY_TRIGGER = 12
SUMMARY_KEEP_RECENT = 8
SESSION_LIST_TTL = 86400 * 7


def _get_redis():
    global _redis, _redis_available
    if not _redis_available:
        return None
    if _redis is None:
        try:
            import redis.asyncio as aioredis
            redis_kwargs = {"decode_responses": True}
            if settings.redis_password:
                redis_kwargs["password"] = settings.redis_password
            _redis = aioredis.from_url(settings.redis_url, **redis_kwargs)
        except Exception as e:
            logger.warning(f"Redis unavailable, using DB only: {e}")
            _redis_available = False
            _redis = None
            return None
    return _redis


# ==================== 会话 CRUD ====================

async def create_session(username: str, title: str = "新对话") -> dict:
    import uuid
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    now = datetime.utcnow()

    conn = await get_db()
    try:
        await execute(conn,
            "INSERT INTO sessions (id, username, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            session_id, username, title, now, now,
        )
    finally:
        await release_db(conn)

    await _invalidate_session_list_cache(username)
    now_iso = now.isoformat()
    return {
        "id": session_id, "username": username, "title": title,
        "summary": "", "message_count": 0,
        "created_at": now_iso, "updated_at": now_iso,
    }


async def list_sessions(username: str) -> list[dict]:
    r = _get_redis()
    cache_key = f"session_list:{username}"
    if r is not None:
        try:
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    conn = await get_db()
    try:
        sessions = await fetchall(conn,
            "SELECT id, username, title, summary, message_count, created_at, updated_at "
            "FROM sessions WHERE username = ? ORDER BY updated_at DESC LIMIT 50",
            username,
        )
    finally:
        await release_db(conn)

    if r is not None and sessions:
        try:
            await r.setex(cache_key, 300, json.dumps(sessions, ensure_ascii=False))
        except Exception:
            pass
    return sessions


async def get_session(session_id: str) -> dict | None:
    r = _get_redis()
    cache_key = f"session_data:{session_id}"
    if r is not None:
        try:
            cached = await r.get(cache_key)
            if cached:
                return json.loads(cached)
        except Exception:
            pass

    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT id, username, title, summary, message_count, created_at, updated_at "
            "FROM sessions WHERE id = ?", session_id,
        )
        if not row:
            return None
        session = dict(row) if isinstance(row, dict) else dict(row)

        messages = await fetchall(conn,
            "SELECT id, session_id, role, content, msg_type, sources, created_at "
            "FROM messages WHERE session_id = ? ORDER BY id ASC",
            session_id,
        )
        session["messages"] = messages
    finally:
        await release_db(conn)

    if r is not None:
        try:
            await r.setex(cache_key, 600, json.dumps(session, ensure_ascii=False))
        except Exception:
            pass
    return session


async def get_session_messages(session_id: str) -> list[dict]:
    conn = await get_db()
    try:
        return await fetchall(conn,
            "SELECT id, session_id, role, content, msg_type, sources, created_at "
            "FROM messages WHERE session_id = ? ORDER BY id ASC",
            session_id,
        )
    finally:
        await release_db(conn)


async def delete_session(session_id: str, username: str) -> bool:
    conn = await get_db()
    try:
        result = await execute(conn,
            "DELETE FROM sessions WHERE id = ? AND username = ?",
            session_id, username,
        )
        deleted = "DELETE" in str(result) if result else False
    finally:
        await release_db(conn)

    if deleted:
        r = _get_redis()
        if r is not None:
            try:
                await r.delete(f"session_data:{session_id}")
            except Exception:
                pass
        await _invalidate_session_list_cache(username)
    return deleted


async def update_session_title(session_id: str, title: str) -> bool:
    conn = await get_db()
    try:
        await execute(conn,
            "UPDATE sessions SET title = ?, updated_at = datetime('now') WHERE id = ?",
            title, session_id,
        )
    finally:
        await release_db(conn)

    await _invalidate_session_cache(session_id)
    return True


async def _invalidate_session_cache(session_id: str):
    r = _get_redis()
    if r is not None:
        try:
            await r.delete(f"session_data:{session_id}")
        except Exception:
            pass


async def _invalidate_session_list_cache(username: str):
    r = _get_redis()
    if r is not None:
        try:
            await r.delete(f"session_list:{username}")
        except Exception:
            pass


# ==================== 消息管理 ====================

async def append_message(session_id: str, role: str, content: str,
                         msg_type: str = "text", sources: list = None) -> dict:
    conn = await get_db()
    try:
        sources_json = json.dumps(sources or [], ensure_ascii=False)
        message_id = await insert_and_get_id(conn,
            "INSERT INTO messages (session_id, role, content, msg_type, sources) VALUES (?, ?, ?, ?, ?)",
            session_id, role, content, msg_type, sources_json,
        )

        await execute(conn,
            "UPDATE sessions SET message_count = message_count + 1, updated_at = datetime('now') WHERE id = ?",
            session_id,
        )

        if role == "user":
            row = await fetchone(conn,
                "SELECT message_count, title FROM sessions WHERE id = ?", session_id,
            )
            if row:
                mc = row["message_count"] if isinstance(row, dict) else row[0] if hasattr(row, '__getitem__') else 0
                title = row.get("title", "新对话") if isinstance(row, dict) else "新对话"
                if mc == 1 and title == "新对话":
                    new_title = content[:30] + ("..." if len(content) > 30 else "")
                    await execute(conn,
                        "UPDATE sessions SET title = ? WHERE id = ?", new_title, session_id,
                    )
    finally:
        await release_db(conn)

    await _invalidate_session_cache(session_id)
    await _invalidate_session_list_cache_for_session(session_id)

    import asyncio
    asyncio.create_task(check_and_summarize(session_id))
    return {"status": "ok", "id": message_id}


def _row_value(row, key):
    """从 asyncpg.Record / sqlite3.Row 中安全取值。"""
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return None


async def add_message_feedback(message_id, feedback: str, username: str) -> dict:
    """记录用户对 AI 回复的赞/踩，并在踩时上报 badcase。"""
    feedback = feedback if feedback in ("helpful", "unhelpful") else "none"

    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT m.id, m.session_id, m.content, s.username "
            "FROM messages m JOIN sessions s ON m.session_id = s.id WHERE m.id = ?",
            message_id,
        )
        if not row:
            return {"status": "not_found"}
        session_id = _row_value(row, "session_id")
        owner = _row_value(row, "username")
        answer = _row_value(row, "content") or ""
        if owner and owner != username:
            return {"status": "forbidden"}

        await execute(conn,
            "UPDATE messages SET feedback = ?, feedback_at = datetime('now') WHERE id = ?",
            feedback, message_id,
        )

        question = ""
        qrow = await fetchone(conn,
            "SELECT content FROM messages WHERE session_id = ? AND role = 'user' AND id < ? ORDER BY id DESC LIMIT 1",
            session_id, message_id,
        )
        question = _row_value(qrow, "content") or ""
    finally:
        await release_db(conn)

    badcase_recorded = False
    if feedback == "unhelpful":
        badcase_recorded = await publish_badcase(session_id, message_id, question, answer, username)

    return {"status": "ok", "feedback": feedback, "badcase_recorded": badcase_recorded}


async def publish_badcase(session_id, message_id, question: str, answer: str, username: str) -> bool:
    """将踩的回复作为 badcase 事件推送到数据中台消费队列。"""
    import uuid
    r = _get_redis()
    if r is None:
        logger.warning("Redis unavailable, badcase not published")
        return False

    event = {
        "event_id": f"badcase_{uuid.uuid4().hex}",
        "source_agent": "orchestrator",
        "event_type": "badcase",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "trace_id": None,
        "user_id": username,
        "payload": {
            "session_id": session_id,
            "message_id": str(message_id),
            "question": question,
            "answer": answer,
            "feedback": "unhelpful",
        },
        "metadata": {"version": "1.0", "schema": "data_platform_v1"},
    }
    try:
        await r.lpush("data_collect", json.dumps(event, ensure_ascii=False))
        return True
    except Exception as e:
        logger.warning(f"Failed to publish badcase: {e}")
        return False


async def _invalidate_session_list_cache_for_session(session_id: str):
    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT username FROM sessions WHERE id = ?", session_id,
        )
        if row:
            username = row["username"] if isinstance(row, dict) else row[0]
            await _invalidate_session_list_cache(username)
    finally:
        await release_db(conn)


# ==================== 摘要压缩 ====================

async def _generate_summary(messages: list[dict]) -> str:
    try:
        import httpx
        conversation = "\n".join([
            f"{'用户' if m['role'] == 'user' else 'AI'}: {m['content'][:200]}"
            for m in messages
        ])

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                f"{settings.siliconflow_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.siliconflow_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "messages": [{
                        "role": "user",
                        "content": f"请用1-2句话总结以下对话的核心内容，保留关键信息：\n\n{conversation}"
                    }],
                    "max_tokens": 200,
                    "temperature": 0.3,
                },
            )
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"Summary generation failed: {e}")
        return ""


async def check_and_summarize(session_id: str):
    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT message_count, summary FROM sessions WHERE id = ?", session_id,
        )
        if not row:
            return

        message_count = row["message_count"] if isinstance(row, dict) else row[0]
        if message_count < SUMMARY_TRIGGER:
            return

        all_messages = await fetchall(conn,
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            session_id,
        )

        to_summarize = all_messages[:message_count - SUMMARY_KEEP_RECENT]
        if len(to_summarize) < 2:
            return

        summary = await _generate_summary(to_summarize)
        if summary:
            old_summary = (row.get("summary") or "") if isinstance(row, dict) else ""
            combined = f"{old_summary}\n{summary}".strip() if old_summary else summary

            await execute(conn,
                "UPDATE sessions SET summary = ?, updated_at = datetime('now') WHERE id = ?",
                combined, session_id,
            )
            await _invalidate_session_cache(session_id)
    finally:
        await release_db(conn)


# ==================== 构建 LLM 上下文 ====================

async def build_chat_context(session_id: str) -> list[dict]:
    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT summary FROM sessions WHERE id = ?", session_id,
        )
        summary = (row.get("summary", "") if isinstance(row, dict) else "") if row else ""

        all_messages = await fetchall(conn,
            "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id ASC",
            session_id,
        )
    finally:
        await release_db(conn)

    context = []
    system_prompt = "你是一个专业的运维 AI 助手，帮助用户解决 IT 运维问题。"
    if summary:
        system_prompt += f"\n\n历史对话摘要：\n{summary}"
    context.append({"role": "system", "content": system_prompt})

    recent = all_messages[-MAX_RECENT_MESSAGES:] if len(all_messages) > MAX_RECENT_MESSAGES else all_messages
    for msg in recent:
        context.append({"role": msg["role"], "content": msg["content"]})
    return context


# ==================== 审计日志 ====================

async def audit_log(username: str, action: str, resource_type: str = "",
                    resource_id: str = "", detail: str = "", ip_address: str = ""):
    conn = await get_db()
    try:
        await execute(conn,
            "INSERT INTO audit_log (username, action, resource_type, resource_id, detail, ip_address) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            username, action, resource_type, resource_id, detail, ip_address,
        )
    finally:
        await release_db(conn)


# ==================== 向后兼容 ====================

async def get_redis_session(session_id: str) -> dict:
    r = _get_redis()
    if r is not None:
        try:
            data = await r.get(f"session:{session_id}")
            if data:
                return json.loads(data)
        except Exception:
            pass
    return {"messages": [], "context": {}}


async def save_redis_session(session_id: str, session_data: dict):
    r = _get_redis()
    if r is not None:
        try:
            await r.setex(f"session:{session_id}", 3600, json.dumps(session_data, ensure_ascii=False))
        except Exception:
            pass