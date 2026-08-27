"""聊天 API - WebSocket + 会话管理 REST API + SSE 流式"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Request, HTTPException, Depends
from fastapi.responses import StreamingResponse
from app.core.session import (
    get_session, append_message, create_session, list_sessions,
    delete_session, get_session_messages, build_chat_context,
    update_session_title, audit_log, add_message_feedback,
)
from app.core.degrader import get_degraded_message
from app.core.tracer import generate_trace_id
from app.core.logger import setup_logger, log_event
from app.core.graph import run_orchestrator
from app.core.router import route_intent
from app.core.mcp_client import mcp_client
from app.api.deps import require_any_authenticated, get_current_user
from app.database import get_db, release_db, fetchone
from app.config import settings
from pydantic import BaseModel
import aiohttp
import asyncio
import json
import time

router = APIRouter()
logger = setup_logger("chat")


# ==================== LLM 降级 ====================

_INTENT_PROMPTS = {
    "consult": "你是一个运维 AI 助手，帮助用户解决 IT 运维问题。请用中文回答，简洁专业。",
    "repair": (
        "你是内部运维报修系统的工单助手。系统会自动创建维修工单并派工程师上门。\n"
        "规则：\n"
        "1. 绝对禁止建议用户联系外部客服（如联想、戴尔、惠普等厂商热线），所有维修由内部工程师处理\n"
        "2. 逐轮收集以下信息，每次只问1个问题：设备类型和型号 -> 故障现象 -> 所在位置（楼层/房间号）-> 联系人\n"
        "3. 用户已提供的信息不要重复追问\n"
        '4. 信息齐全后告知用户"工单已生成，工程师将尽快上门处理"\n'
        "5. 回复简洁，不超过3句话，使用中文"
    ),
    "warehouse_op": "你是一个库房管理助手。请帮助用户查询库存、记录出入库操作。",
    "check_progress": "你是一个工单查询助手。请帮助用户查询工单进度和状态。",
    "spare_request": "你是一个备件管理助手。请帮助用户提交和管理备件申请。",
}


async def _llm_fallback(message: str, context: list[dict], intent: str, agent: str) -> str:
    """Agent 不可用时，直接调用 LLM 处理"""
    if not settings.siliconflow_api_key:
        logger.warning(f"LLM fallback: no API key configured")
        return get_degraded_message(agent)

    system_prompt = _INTENT_PROMPTS.get(intent, _INTENT_PROMPTS["consult"])
    messages = [{"role": "system", "content": system_prompt}]
    # 只取最近几条上下文
    for msg in context[-6:]:
        if msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"][:500]})
    messages.append({"role": "user", "content": message})

    try:
        timeout = aiohttp.ClientTimeout(total=60, connect=10)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{settings.siliconflow_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.siliconflow_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "max_tokens": 800,
                    "temperature": 0.7,
                },
            ) as response:
                logger.info(f"LLM fallback: status={response.status}")
                data = await response.json()
                if response.status != 200:
                    logger.error(f"LLM fallback: API error {response.status}: {data}")
                    return get_degraded_message(agent)
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not content:
                    logger.error(f"LLM fallback: empty content, data={data}")
                    return get_degraded_message(agent)
                return content.strip()
    except Exception as e:
        logger.error(f"LLM fallback failed: {type(e).__name__}: {e}")
        return get_degraded_message(agent)


# ==================== REST API: 会话管理 ====================

class CreateSessionRequest(BaseModel):
    title: str = "新对话"


class UpdateTitleRequest(BaseModel):
    title: str


class FeedbackRequest(BaseModel):
    feedback: str  # helpful / unhelpful


@router.post("/api/v1/chat/messages/{message_id}/feedback")
async def api_message_feedback(
    message_id: int,
    body: FeedbackRequest,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    """对 AI 回复消息进行赞/踩，踩时会自动上报 badcase。"""
    result = await add_message_feedback(message_id, body.feedback, user["username"])
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="消息不存在")
    if result.get("status") == "forbidden":
        raise HTTPException(status_code=403, detail="无权操作此消息")
    await audit_log(user["username"], "feedback", "message", str(message_id),
                    f"反馈: {body.feedback}")
    return result


@router.get("/api/v1/chat/sessions")
async def api_list_sessions(request: Request, user: dict = Depends(require_any_authenticated)):
    username = user["username"]
    sessions = await list_sessions(username)
    return {"sessions": sessions}


@router.post("/api/v1/chat/sessions")
async def api_create_session(
    body: CreateSessionRequest,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    session = await create_session(user["username"], body.title)
    await audit_log(user["username"], "create_session", "session", session["id"],
                    f"创建会话: {body.title}")
    return session


@router.get("/api/v1/chat/sessions/{session_id}")
async def api_get_session(
    session_id: str,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")
    if session["username"] != user["username"]:
        raise HTTPException(status_code=403, detail="无权访问此会话")
    return session


@router.get("/api/v1/chat/sessions/{session_id}/messages")
async def api_get_messages(
    session_id: str,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT username FROM sessions WHERE id = ?", session_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在")
        username = row["username"] if isinstance(row, dict) else row[0]
        if username != user["username"]:
            raise HTTPException(status_code=403, detail="无权访问此会话")
    finally:
        await release_db(conn)

    messages = await get_session_messages(session_id)
    return {"messages": messages}


@router.delete("/api/v1/chat/sessions/{session_id}")
async def api_delete_session(
    session_id: str,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    deleted = await delete_session(session_id, user["username"])
    if not deleted:
        raise HTTPException(status_code=404, detail="会话不存在或无权删除")
    await audit_log(user["username"], "delete_session", "session", session_id)
    return {"status": "ok"}


@router.put("/api/v1/chat/sessions/{session_id}/title")
async def api_update_title(
    session_id: str,
    body: UpdateTitleRequest,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT username FROM sessions WHERE id = ?", session_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在")
        username = row["username"] if isinstance(row, dict) else row[0]
        if username != user["username"]:
            raise HTTPException(status_code=403, detail="无权修改此会话")
    finally:
        await release_db(conn)

    await update_session_title(session_id, body.title)
    return {"status": "ok"}


# ==================== WebSocket: 聊天 ====================

@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str, token: str = Query(None)):
    if not token:
        await websocket.close(code=4001, reason="Missing authentication token")
        return

    try:
        import jwt
        from app.config import settings
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        username = payload.get("sub")
        if not username:
            await websocket.close(code=4001, reason="Invalid token")
            return
    except jwt.PyJWTError:
        await websocket.close(code=4001, reason="Invalid or expired token")
        return

    await websocket.accept()
    trace_id = generate_trace_id()

    session = await get_session(session_id)
    if session and session.get("username") != username:
        await websocket.send_json({
            "type": "error",
            "payload": {"message": "无权访问此会话"},
        })
        await websocket.close(code=4003, reason="Forbidden")
        return

    try:
        while True:
            data = await websocket.receive_json()
            payload_data = data.get("payload", {})
            message = payload_data.get("content", "") or data.get("message", "")

            if not message:
                continue

            await append_message(session_id, "user", message)
            context = await build_chat_context(session_id)

            await websocket.send_json({
                "type": "reply_start",
                "payload": {"message": "processing"},
            })

            orch_result = await run_orchestrator(
                message=message,
                session_id=session_id,
                context=context,
                trace_id=trace_id,
                user_info={"username": username},
            )

            reply_text = orch_result["reply"]
            sources = orch_result.get("sources", [])

            await websocket.send_json({
                "type": "reply_chunk",
                "payload": {"content": reply_text},
            })

            await append_message(session_id, "assistant", reply_text, sources=sources)

            await websocket.send_json({
                "type": "reply_end",
                "payload": {
                    "intent": orch_result["intent"],
                    "agent": orch_result["agent"],
                    "confidence": orch_result["confidence"],
                    "sources": [{"title": s, "score": 0.8} for s in sources],
                    "degraded_agents": orch_result.get("degraded_agents", []),
                    "trace_id": trace_id,
                },
            })

    except WebSocketDisconnect:
        log_event(logger, "ws_disconnected", trace_id=trace_id, session_id=session_id)
    except Exception as e:
        log_event(logger, "ws_error", level="ERROR", trace_id=trace_id, error=str(e))


# ==================== REST 聊天端点（替代 WebSocket，解决超时问题） ====================

class SendMessageRequest(BaseModel):
    content: str
    msg_type: str = "text"


@router.post("/api/v1/chat/sessions/{session_id}/messages")
async def api_send_message(
    session_id: str,
    body: SendMessageRequest,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    """REST 接口发送消息并获取 AI 回复"""
    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT username FROM sessions WHERE id = ?", session_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在")
        username = row["username"] if isinstance(row, dict) else row[0]
        if username != user["username"]:
            raise HTTPException(status_code=403, detail="无权访问此会话")
    finally:
        await release_db(conn)

    message = body.content
    trace_id = getattr(request.state, "trace_id", None) or generate_trace_id()

    # 丰富用户信息：从数据库查询 display_name 和 email
    user_info = dict(user)
    conn2 = await get_db()
    try:
        user_row = await fetchone(conn2,
            "SELECT display_name, email FROM users WHERE username = ?", user["username"],
        )
        if user_row:
            user_info["display_name"] = (user_row["display_name"] if isinstance(user_row, dict) else user_row[0]) or ""
            user_info["email"] = (user_row["email"] if isinstance(user_row, dict) else user_row[1]) or ""
    finally:
        await release_db(conn2)

    await append_message(session_id, "user", message)
    context = await build_chat_context(session_id)

    orch_result = await run_orchestrator(
        message=message,
        session_id=session_id,
        context=context,
        trace_id=trace_id,
        user_info=user_info,
    )

    reply_text = orch_result["reply"]
    sources = orch_result.get("sources", [])

    await append_message(session_id, "assistant", reply_text, sources=sources)

    return {
        "reply": reply_text,
        "intent": orch_result["intent"],
        "agent": orch_result["agent"],
        "confidence": orch_result["confidence"],
        "sources": [{"title": s, "score": 0.8} for s in sources],
        "degraded_agents": orch_result.get("degraded_agents", []),
        "trace_id": trace_id,
    }


# ==================== SSE 流式聊天 ====================

RAG_QA_PROMPT = """你是运维助手。请根据以下运维知识库的内容回答用户问题或提供建议。

回答规则：
1. 优先使用知识库中的内容直接回答，提供具体的排查步骤和解决方案
2. 即使用户只是描述问题而非提问，也请主动提供相关的故障排查建议
3. 如果知识库内容与用户问题完全不相关，请回复："抱歉，我暂时无法解答这个问题。请尝试换个方式描述您的问题，或联系运维团队获取进一步帮助。"
4. 不要主动提及创建工单、报修工单等——工单相关操作由其他系统处理，你只需专注于技术排查和建议

知识库参考内容：
{context}

<user_question>
{question}
</user_question>

请用中文回答，保持专业、简洁，直接给出解决方案。"""


async def _fetch_rag_context(query: str, history: list[dict], trace_id: str) -> str:
    """调用 ops-agent 的 rag_search 获取知识库上下文"""
    try:
        result = await mcp_client.call_tool(
            agent_name="ops-agent",
            tool_name="rag_search",
            arguments={"query": query, "top_k": 5, "history": history},
            trace_id=trace_id,
            retries=1,  # RAG 检索对实时性敏感，减少重试
        )
        if result.get("error"):
            logger.warning(f"RAG search failed: {result['error']}")
            return ""
        data = result.get("result", {})
        docs = data.get("documents", []) or data.get("data", {}).get("documents", [])
        if not docs:
            return ""
        return "\n\n".join([
            f"[来源 {i+1}] {d.get('content', str(d))}"
            for i, d in enumerate(docs[:5])
        ])
    except Exception as e:
        logger.error(f"RAG search error: {e}")
        return ""


async def _stream_llm_response(messages: list[dict], trace_id: str):
    """流式调用 LLM，逐 token 产出 SSE 事件"""
    if not settings.siliconflow_api_key:
        yield f"data: {json.dumps({'error': 'LLM not configured'})}\n\n"
        return

    start_time = time.time()
    try:
        timeout = aiohttp.ClientTimeout(total=120, connect=10, sock_read=120)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                f"{settings.siliconflow_base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.siliconflow_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": settings.llm_model,
                    "messages": messages,
                    "max_tokens": 1200,
                    "temperature": 0.7,
                    "stream": True,
                },
            ) as response:
                if response.status != 200:
                    body = await response.text()
                    logger.error(f"LLM stream error {response.status}: {body}")
                    yield f"data: {json.dumps({'error': f'LLM API error: {response.status}'})}\n\n"
                    return

                full_content = ""
                async for line in response.content:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data_str)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        content = delta.get("content", "")
                        if content:
                            full_content += content
                            yield f"data: {json.dumps({'token': content})}\n\n"
                    except json.JSONDecodeError:
                        continue

                elapsed = time.time() - start_time
                logger.info(f"LLM stream completed: {len(full_content)} chars in {elapsed:.1f}s")
                yield f"data: {json.dumps({'done': True, 'total_chars': len(full_content)})}\n\n"

    except Exception as e:
        logger.error(f"LLM stream failed: {type(e).__name__}: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.post("/api/v1/chat/sessions/{session_id}/stream")
async def api_send_message_stream(
    session_id: str,
    body: SendMessageRequest,
    request: Request,
    user: dict = Depends(require_any_authenticated),
):
    """SSE 流式发送消息并获取 AI 回复"""
    conn = await get_db()
    try:
        row = await fetchone(conn,
            "SELECT username FROM sessions WHERE id = ?", session_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail="会话不存在")
        username = row["username"] if isinstance(row, dict) else row[0]
        if username != user["username"]:
            raise HTTPException(status_code=403, detail="无权访问此会话")
    finally:
        await release_db(conn)

    message = body.content
    trace_id = getattr(request.state, "trace_id", None) or generate_trace_id()

    # 丰富用户信息：从数据库查询 display_name 和 email
    user_info = dict(user)
    conn2 = await get_db()
    try:
        user_row = await fetchone(conn2,
            "SELECT display_name, email FROM users WHERE username = ?", user["username"],
        )
        if user_row:
            user_info["display_name"] = (user_row["display_name"] if isinstance(user_row, dict) else user_row[0]) or ""
            user_info["email"] = (user_row["email"] if isinstance(user_row, dict) else user_row[1]) or ""
    finally:
        await release_db(conn2)

    await append_message(session_id, "user", message)
    context = await build_chat_context(session_id)

    route_result = route_intent(message, trace_id, session_id)
    intent = route_result["intent"]

    async def event_stream():
        full_reply = ""
        sources = []
        agent = ""

        try:
            if intent == "consult":
                # 1. 先获取 RAG 上下文
                rag_context = await _fetch_rag_context(message, context, trace_id)
                if rag_context:
                    sources = [s.split("\n")[0][:80] for s in rag_context.split("\n\n") if s.strip()]
                    yield f"data: {json.dumps({'sources': sources})}\n\n"

                # 2. 构建消息
                system_prompt = RAG_QA_PROMPT.format(context=rag_context, question=message) if rag_context else \
                    "你是一个运维 AI 助手，帮助用户解决 IT 运维问题。请用中文回答，简洁专业。"
                messages = [{"role": "system", "content": system_prompt}]
                for msg in context[-6:]:
                    if msg.get("role") in ("user", "assistant"):
                        messages.append({"role": msg["role"], "content": msg["content"][:500]})
                messages.append({"role": "user", "content": message})

                # 3. 流式输出 LLM（内部 done 事件不转发，统一在 finally 携带 message_id 发送）
                async for event in _stream_llm_response(messages, trace_id):
                    try:
                        data = json.loads(event[6:])
                    except (json.JSONDecodeError, IndexError):
                        continue
                    if "error" in data:
                        yield event
                    elif "token" in data:
                        full_reply += data["token"]
                        yield event
            else:
                # 非 consult 意图：直接走 graph 流程，reply 逐字流式输出
                orch_result = await run_orchestrator(
                    message=message,
                    session_id=session_id,
                    context=context,
                    trace_id=trace_id,
                    user_info=user_info,
                )
                full_reply = orch_result["reply"]
                agent = orch_result.get("agent", "")
                # 逐字流式输出 graph 的回复
                for ch in full_reply:
                    yield f"data: {json.dumps({'token': ch})}\n\n"
                    await asyncio.sleep(0.02)  # 模拟流式效果，约50字/秒

        except Exception as e:
            logger.error(f"Stream error: {type(e).__name__}: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # 保存完整回复，并携带服务端真实消息 id（供前端赞/踩定位数据库记录）
            assistant_msg_id = None
            if full_reply:
                result = await append_message(session_id, "assistant", full_reply, sources=sources)
                assistant_msg_id = result.get("id") if isinstance(result, dict) else None
            yield f"data: {json.dumps({'done': True, 'message_id': assistant_msg_id, 'intent': intent, 'agent': agent})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==================== 向后兼容路由（/api/ 前缀） ====================

@router.get("/api/chat/sessions")
async def api_list_sessions_v0(request: Request, user: dict = Depends(require_any_authenticated)):
    return await api_list_sessions(request, user)

@router.post("/api/chat/sessions")
async def api_create_session_v0(body: CreateSessionRequest, request: Request, user: dict = Depends(require_any_authenticated)):
    return await api_create_session(body, request, user)

@router.get("/api/chat/sessions/{session_id}")
async def api_get_session_v0(session_id: str, request: Request, user: dict = Depends(require_any_authenticated)):
    return await api_get_session(session_id, request, user)

@router.get("/api/chat/sessions/{session_id}/messages")
async def api_get_messages_v0(session_id: str, request: Request, user: dict = Depends(require_any_authenticated)):
    return await api_get_messages(session_id, request, user)

@router.delete("/api/chat/sessions/{session_id}")
async def api_delete_session_v0(session_id: str, request: Request, user: dict = Depends(require_any_authenticated)):
    return await api_delete_session(session_id, request, user)

@router.put("/api/chat/sessions/{session_id}/title")
async def api_update_title_v0(session_id: str, body: UpdateTitleRequest, request: Request, user: dict = Depends(require_any_authenticated)):
    return await api_update_title(session_id, body, request, user)