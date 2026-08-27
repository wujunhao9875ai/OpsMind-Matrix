"""
项目1（Ops Agent）验收测试脚本
测试目标：运维 AI 平台 - 智能客服 Agent
后端地址：http://127.0.0.1:8000
"""
import requests
import json
import time
import uuid
import sys
import traceback

BASE = "http://127.0.0.1:8000"
TIMEOUT = 120  # LLM 降级需要时间，设置较长超时

ACCOUNTS = {
    "admin":     {"username": "admin",      "password": "Admin@2024Demo"},
    "engineer1": {"username": "engineer1",  "password": "Engineer@123"},
    "testuser":  {"username": "testuser",   "password": "User@123"},
    "storekeeper": {"username": "storekeeper", "password": "storekeeper123"},
}

PASS = 0
FAIL = 0
SKIP = 0


def test(name, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name} {detail}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")
    return condition


def skip(name, detail=""):
    global SKIP
    SKIP += 1
    print(f"  [SKIP] {name} {detail}")


def login(username, password):
    """登录并返回 token，失败返回 None"""
    try:
        r = requests.post(
            f"{BASE}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if r.status_code == 200:
            return r.json().get("access_token")
        return None
    except Exception:
        return None


# ============================================================
# 测试 1: 员工可通过 Web 界面登录
# ============================================================
print("=" * 60)
print("  测试 1: 员工登录（POST /api/v1/auth/login）")
print("=" * 60)

tokens = {}
for role, acc in ACCOUNTS.items():
    token = login(acc["username"], acc["password"])
    if token:
        tokens[role] = token
        test(f"{role} 登录", True, f"token={token[:20]}...")
    else:
        test(f"{role} 登录", False, "未获取到 token")

# 错误密码
r = requests.post(f"{BASE}/api/v1/auth/login", json={"username": "admin", "password": "wrong"}, timeout=10)
test("错误密码拒绝", r.status_code == 401, f"status={r.status_code}")

# 不存在用户
r = requests.post(f"{BASE}/api/v1/auth/login", json={"username": "nobody_x", "password": "x"}, timeout=10)
test("不存在用户拒绝", r.status_code == 401, f"status={r.status_code}")

if not tokens.get("testuser"):
    print("\n  [ABORT] 无可用测试账号，终止后续测试")
    print(f"\n  结果: {PASS} 通过, {FAIL} 失败, {SKIP} 跳过")
    sys.exit(1)


# ============================================================
# 测试 2: AI 能在 20 秒内给出回答
# ============================================================
print("\n" + "=" * 60)
print("  测试 2: AI 响应时间（POST /api/v1/chat/sessions/{id}/messages）")
print("=" * 60)

user_token = tokens["testuser"]
auth_headers = {"Authorization": f"Bearer {user_token}"}

# 创建会话
r = requests.post(
    f"{BASE}/api/v1/chat/sessions",
    json={"title": "验收测试-响应时间"},
    headers=auth_headers,
    timeout=10,
)
if r.status_code in (200, 201):
    session_data = r.json()
    sid = session_data.get("id") or session_data.get("session_id")
    test("创建会话", True, f"session_id={sid}")
else:
    test("创建会话", False, f"status={r.status_code} {r.text[:100]}")
    sid = None

if sid:
    start = time.time()
    try:
        r = requests.post(
            f"{BASE}/api/v1/chat/sessions/{sid}/messages",
            json={"content": "你好，请介绍一下你自己"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )
        elapsed = time.time() - start
        ok = r.status_code == 200
        has_reply = bool(r.json().get("reply"))
        fast_enough = elapsed < 20

        test("HTTP 200", ok, f"status={r.status_code}")
        test("有回复内容", has_reply, f"reply={r.json().get('reply', '')[:80]}...")
        test(f"响应时间 < 20s", fast_enough, f"耗时={elapsed:.1f}s")
        print(f"    intent={r.json().get('intent')}, agent={r.json().get('agent')}")
    except requests.Timeout:
        test("响应时间 < 20s", False, "请求超时")
    except Exception as e:
        test("AI 响应", False, f"异常: {e}")


# ============================================================
# 测试 3: 报修场景多轮追问
# ============================================================
print("\n" + "=" * 60)
print("  测试 3: 报修场景多轮追问（意图 = repair）")
print("=" * 60)

# 创建新会话用于报修测试
r = requests.post(
    f"{BASE}/api/v1/chat/sessions",
    json={"title": "验收测试-报修多轮"},
    headers=auth_headers,
    timeout=10,
)
if r.status_code in (200, 201):
    repair_sid = r.json().get("id") or r.json().get("session_id")
    test("创建报修会话", True, f"session_id={repair_sid}")
else:
    test("创建报修会话", False, f"status={r.status_code}")
    repair_sid = None

if repair_sid:
    rounds = [
        ("打印机坏了", "repair"),
        ("5楼", "repair"),
        ("打印出来全是黑条", "repair"),
    ]

    for i, (msg, expected_intent) in enumerate(rounds, 1):
        try:
            r = requests.post(
                f"{BASE}/api/v1/chat/sessions/{repair_sid}/messages",
                json={"content": msg},
                headers=auth_headers,
                timeout=TIMEOUT,
            )
            actual_intent = r.json().get("intent", "")
            has_reply = bool(r.json().get("reply"))
            intent_match = actual_intent == expected_intent

            test(
                f"第{i}轮 intent={expected_intent}",
                intent_match,
                f"actual={actual_intent} reply={r.json().get('reply', '')[:60]}...",
            )
            if not has_reply:
                print(f"    [WARN] 第{i}轮无回复内容")
        except requests.Timeout:
            test(f"第{i}轮超时", False, "请求超时")
        except Exception as e:
            test(f"第{i}轮异常", False, f"{e}")


# ============================================================
# 测试 4: 聊天记录持久化
# ============================================================
print("\n" + "=" * 60)
print("  测试 4: 聊天记录持久化（GET /api/v1/chat/sessions/{id}/messages）")
print("=" * 60)

# 创建独立会话
r = requests.post(
    f"{BASE}/api/v1/chat/sessions",
    json={"title": "验收测试-持久化"},
    headers=auth_headers,
    timeout=10,
)
if r.status_code in (200, 201):
    persist_sid = r.json().get("id") or r.json().get("session_id")
    test("创建持久化会话", True, f"session_id={persist_sid}")
else:
    test("创建持久化会话", False, f"status={r.status_code}")
    persist_sid = None

if persist_sid:
    # 发送消息
    try:
        r = requests.post(
            f"{BASE}/api/v1/chat/sessions/{persist_sid}/messages",
            json={"content": "电脑蓝屏怎么处理"},
            headers=auth_headers,
            timeout=TIMEOUT,
        )
        send_ok = r.status_code == 200
        test("发送消息成功", send_ok, f"status={r.status_code}")
    except Exception as e:
        test("发送消息", False, f"异常: {e}")
        send_ok = False

    if send_ok:
        # 查询消息列表
        r = requests.get(
            f"{BASE}/api/v1/chat/sessions/{persist_sid}/messages",
            headers=auth_headers,
            timeout=10,
        )
        get_ok = r.status_code == 200
        test("查询消息列表", get_ok, f"status={r.status_code}")

        if get_ok:
            data = r.json()
            messages = data.get("messages", data if isinstance(data, list) else [])
            msg_count = len(messages)
            has_user = any(m.get("role") == "user" for m in messages)
            has_assistant = any(m.get("role") == "assistant" for m in messages)

            test(f"消息列表非空", msg_count > 0, f"共 {msg_count} 条")
            test(f"包含用户消息", has_user)
            test(f"包含 AI 回复", has_assistant)
            if has_user:
                user_msgs = [m["content"][:40] for m in messages if m.get("role") == "user"]
                print(f"    用户消息: {user_msgs}")
        else:
            skip("消息内容验证", "消息列表查询失败")

    # 会话列表验证
    r = requests.get(f"{BASE}/api/v1/chat/sessions", headers=auth_headers, timeout=10)
    if r.status_code == 200:
        data = r.json()
        sessions = data.get("sessions", data if isinstance(data, list) else [])
        session_ids = [s.get("id") or s.get("session_id") for s in sessions]
        found = persist_sid in session_ids
        test(f"会话出现在列表中", found, f"共 {len(sessions)} 个会话")
    else:
        test("会话列表查询", False, f"status={r.status_code}")


# ============================================================
# 测试 5: 反馈功能（留空 - 前端功能）
# ============================================================
print("\n" + "=" * 60)
print("  测试 5: 反馈功能")
print("=" * 60)
skip("反馈功能", "前端功能，不在本次验收范围")


# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL + SKIP
print(f"  验收测试完成: {PASS} 通过, {FAIL} 失败, {SKIP} 跳过, 共 {total} 项")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)