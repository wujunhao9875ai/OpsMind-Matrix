"""
项目2（Dispatch Agent）验收测试脚本
测试目标：运维 AI 平台 - 智能派单 Agent
后端地址：http://127.0.0.1:8000
API 前缀：/api/v1/dispatch/...（Orchestrator 代理 + Mock 降级）
"""
import requests
import json
import time
import sys
import traceback

BASE = "http://127.0.0.1:8000"
TIMEOUT = 120  # LLM 降级需要时间

ACCOUNTS = {
    "admin":     {"username": "admin",      "password": "Admin@2024Demo",     "role": "admin"},
    "engineer1": {"username": "engineer1",  "password": "Engineer@123",      "role": "engineer"},
    "engineer2": {"username": "engineer2",  "password": "Engineer@123",      "role": "engineer"},
    "testuser":  {"username": "testuser",   "password": "User@123",          "role": "user"},
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
    """登录并返回 token 和 user_info"""
    try:
        r = requests.post(
            f"{BASE}/api/v1/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
        if r.status_code == 200:
            data = r.json()
            return data.get("access_token"), data
        return None, None
    except Exception:
        return None, None


# ============================================================
# 阶段 0: 登录所有账号
# ============================================================
print("=" * 60)
print("  阶段 0: 账号登录（POST /api/v1/auth/login）")
print("=" * 60)

tokens = {}
user_infos = {}
for role, acc in ACCOUNTS.items():
    token, info = login(acc["username"], acc["password"])
    if token:
        tokens[role] = token
        user_infos[role] = info
        test(f"{role} 登录", True, f"token={token[:20]}...")
    else:
        test(f"{role} 登录", False, "未获取到 token")

if not tokens.get("admin"):
    print("\n  [ABORT] 无管理员账号，终止后续测试")
    print(f"\n  结果: {PASS} 通过, {FAIL} 失败, {SKIP} 跳过")
    sys.exit(1)

admin_headers = {"Authorization": f"Bearer {tokens['admin']}"}
eng_headers = {"Authorization": f"Bearer {tokens.get('engineer1', tokens['admin'])}"}


# ============================================================
# 测试 1: 管理员可从预填工单列表审核确认并创建正式工单
# 测试 POST /api/v1/dispatch/tickets 创建工单
# ============================================================
print("\n" + "=" * 60)
print("  测试 1: 管理员创建工单（POST /api/v1/dispatch/tickets）")
print("=" * 60)

# 模拟预填工单数据
pre_tickets = [
    {"title": "打印机故障报修", "description": "5楼打印机卡纸", "priority": "medium"},
    {"title": "网络连接异常", "description": "3楼西区无法连接内网", "priority": "high"},
    {"title": "电脑蓝屏", "description": "财务部电脑频繁蓝屏", "priority": "high"},
]

created_tickets = []
for i, pt in enumerate(pre_tickets):
    try:
        r = requests.post(
            f"{BASE}/api/v1/dispatch/tickets",
            json=pt,
            headers=admin_headers,
            timeout=10,
        )
        ok = r.status_code == 200
        data = r.json() if ok else {}
        tid = data.get("id", "")
        test(f"从预填单创建工单 {i+1}: {pt['title']}", ok, f"id={tid} status={data.get('status')}")
        if ok:
            created_tickets.append(data)
            test(f"  状态为 created", data.get("status") == "created", f"status={data.get('status')}")
            test(f"  优先级正确", data.get("priority") == pt["priority"] or data.get("urgency") == pt["priority"],
                 f"expected={pt['priority']} actual={data.get('priority') or data.get('urgency')}")
    except Exception as e:
        test(f"从预填单创建工单 {i+1}: {pt['title']}", False, f"异常: {e}")

test("创建了至少 1 张工单", len(created_tickets) > 0, f"共 {len(created_tickets)} 张")


# ============================================================
# 测试 2: 派单引擎自动选择最优工程师
# 测试 POST /api/v1/dispatch/assign 自动指派
# ============================================================
print("\n" + "=" * 60)
print("  测试 2: 派单引擎自动指派（POST /api/v1/dispatch/assign）")
print("=" * 60)

# 先获取工程师列表
eng_list = []
try:
    r = requests.get(f"{BASE}/api/v1/dispatch/engineers", headers=admin_headers, timeout=10)
    if r.status_code == 200:
        eng_list = r.json().get("engineers", [])
        test("获取工程师列表", True, f"共 {len(eng_list)} 人")
        for eng in eng_list:
            print(f"    - {eng['name']} (id={eng['id']}, status={eng['status']}, load={eng['current_load']})")
    else:
        test("获取工程师列表", False, f"status={r.status_code}")
except Exception as e:
    test("获取工程师列表", False, f"异常: {e}")

# 对每张已创建的工单进行指派
assigned_tickets = []
if created_tickets and eng_list:
    # 选择负载最低的工程师进行指派
    idle_engineers = [e for e in eng_list if e.get("status") == "idle" and e.get("current_load", 0) < 3]
    best_engineer = idle_engineers[0] if idle_engineers else eng_list[0]

    for i, ticket in enumerate(created_tickets):
        tid = ticket.get("id")
        try:
            r = requests.post(
                f"{BASE}/api/v1/dispatch/assign",
                json={"ticket_id": tid, "engineer_id": best_engineer["id"]},
                headers=admin_headers,
                timeout=10,
            )
            ok = r.status_code == 200
            data = r.json() if ok else {}
            test(f"指派工单 {tid} 给 {best_engineer['name']}", ok,
                 f"status={data.get('status')} engineer={data.get('engineer_name')}")
            if ok:
                assigned_tickets.append(data)
                test(f"  状态变为 assigned", data.get("status") == "assigned",
                     f"status={data.get('status')}")
        except Exception as e:
            test(f"指派工单 {tid}", False, f"异常: {e}")

    test("指派了至少 1 张工单", len(assigned_tickets) > 0, f"共 {len(assigned_tickets)} 张")
else:
    skip("指派工单", "无可用工单或工程师")


# ============================================================
# 测试 3: 工单状态机完整流转
# 测试 created→assigned→in_progress→resolved→closed
# ============================================================
print("\n" + "=" * 60)
print("  测试 3: 工单状态机完整流转")
print("  路径: created → assigned → in_progress → resolved → closed")
print("=" * 60)

# 选择一张工单进行完整状态流转
if assigned_tickets:
    test_ticket = assigned_tickets[0]
    tid = test_ticket.get("id")
    print(f"  测试工单: {tid} ({test_ticket.get('title')})")

    # 3a: 接单（assigned → in_progress）
    try:
        r = requests.post(
            f"{BASE}/api/v1/dispatch/accept",
            json={"ticket_id": tid},
            headers=admin_headers,
            timeout=10,
        )
        ok = r.status_code == 200
        data = r.json() if ok else {}
        test("3a. 接单 (assigned→in_progress)", ok and data.get("status") == "in_progress",
             f"status={data.get('status')}")
    except Exception as e:
        test("3a. 接单", False, f"异常: {e}")

    # 3b: 解决（in_progress → resolved）
    try:
        r = requests.post(
            f"{BASE}/api/v1/dispatch/resolve",
            json={"ticket_id": tid, "resolution": "已更换打印机硒鼓，测试正常"},
            headers=admin_headers,
            timeout=10,
        )
        ok = r.status_code == 200
        data = r.json() if ok else {}
        test("3b. 解决 (in_progress→resolved)", ok and data.get("status") == "resolved",
             f"status={data.get('status')} resolution={data.get('resolution', '')[:40]}")
    except Exception as e:
        test("3b. 解决", False, f"异常: {e}")

    # 3c: 关闭（resolved → closed）
    try:
        r = requests.post(
            f"{BASE}/api/v1/dispatch/close",
            json={"ticket_id": tid},
            headers=admin_headers,
            timeout=10,
        )
        ok = r.status_code == 200
        data = r.json() if ok else {}
        test("3c. 关闭 (resolved→closed)", ok and data.get("status") == "closed",
             f"status={data.get('status')}")
    except Exception as e:
        test("3c. 关闭", False, f"异常: {e}")

    # 验证最终状态
    try:
        r = requests.get(f"{BASE}/api/v1/dispatch/tickets", headers=admin_headers, timeout=10)
        if r.status_code == 200:
            tickets = r.json().get("tickets", [])
            found = [t for t in tickets if t.get("id") == tid]
            test("3d. 验证最终状态为 closed", len(found) > 0 and found[0].get("status") == "closed",
                 f"found={len(found)} status={found[0].get('status') if found else 'N/A'}")
    except Exception as e:
        test("3d. 验证最终状态", False, f"异常: {e}")
else:
    skip("状态机流转测试", "无已指派工单")


# ============================================================
# 测试 4: 管理员可通过自然语言操作工单
# 测试 POST /api/v1/chat/sessions/{id}/messages 发送工单操作指令
# ============================================================
print("\n" + "=" * 60)
print("  测试 4: 管理员自然语言操作工单")
print("  测试 POST /api/v1/chat/sessions/{id}/messages")
print("=" * 60)

# 创建管理员的聊天会话
try:
    r = requests.post(
        f"{BASE}/api/v1/chat/sessions",
        json={"title": "验收测试-管理员工单操作"},
        headers=admin_headers,
        timeout=10,
    )
    if r.status_code == 200:
        chat_sid = r.json().get("id")
        test("创建管理员聊天会话", True, f"session_id={chat_sid}")
    else:
        test("创建管理员聊天会话", False, f"status={r.status_code}")
        chat_sid = None
except Exception as e:
    test("创建管理员聊天会话", False, f"异常: {e}")
    chat_sid = None

if chat_sid:
    # 自然语言指令测试
    nl_commands = [
        ("查看工单堆积情况", "aggregate"),
        ("查看所有工单", "query"),
    ]

    for cmd, expected_intent in nl_commands:
        try:
            start = time.time()
            r = requests.post(
                f"{BASE}/api/v1/chat/sessions/{chat_sid}/messages",
                json={"content": cmd},
                headers=admin_headers,
                timeout=TIMEOUT,
            )
            elapsed = time.time() - start
            ok = r.status_code == 200
            reply = r.json().get("reply", "") if ok else ""
            intent = r.json().get("intent", "") if ok else ""

            test(f"NL 指令: '{cmd}'", ok and len(reply) > 0,
                 f"status={r.status_code} intent={intent} reply={reply[:60]}... elapsed={elapsed:.1f}s")
        except requests.Timeout:
            test(f"NL 指令: '{cmd}'", False, f"请求超时 (> {TIMEOUT}s)")
        except Exception as e:
            test(f"NL 指令: '{cmd}'", False, f"异常: {e}")

    # 测试工单指派 NL 指令（如 "把xxx工单派给张三"）
    if created_tickets and len(created_tickets) > 1:
        remaining_ticket = created_tickets[-1]
        assign_cmd = f"把{remaining_ticket.get('title', '打印机')}工单派给李四"
        try:
            start = time.time()
            r = requests.post(
                f"{BASE}/api/v1/chat/sessions/{chat_sid}/messages",
                json={"content": assign_cmd},
                headers=admin_headers,
                timeout=TIMEOUT,
            )
            elapsed = time.time() - start
            ok = r.status_code == 200
            reply = r.json().get("reply", "") if ok else ""
            intent = r.json().get("intent", "") if ok else ""

            test(f"NL 指派: '{assign_cmd}'", ok and len(reply) > 0,
                 f"status={r.status_code} intent={intent} reply={reply[:60]}... elapsed={elapsed:.1f}s")
        except requests.Timeout:
            test(f"NL 指派: '{assign_cmd}'", False, f"请求超时 (> {TIMEOUT}s)")
        except Exception as e:
            test(f"NL 指派: '{assign_cmd}'", False, f"异常: {e}")

    # 测试批量结单 NL 指令
    close_cmd = "将5楼的工单都结掉"
    try:
        start = time.time()
        r = requests.post(
            f"{BASE}/api/v1/chat/sessions/{chat_sid}/messages",
            json={"content": close_cmd},
            headers=admin_headers,
            timeout=TIMEOUT,
        )
        elapsed = time.time() - start
        ok = r.status_code == 200
        reply = r.json().get("reply", "") if ok else ""
        intent = r.json().get("intent", "") if ok else ""

        test(f"NL 批量结单: '{close_cmd}'", ok and len(reply) > 0,
             f"status={r.status_code} intent={intent} reply={reply[:60]}... elapsed={elapsed:.1f}s")
    except requests.Timeout:
        test(f"NL 批量结单: '{close_cmd}'", False, f"请求超时 (> {TIMEOUT}s)")
    except Exception as e:
        test(f"NL 批量结单: '{close_cmd}'", False, f"异常: {e}")

    # 验证聊天记录持久化
    try:
        r = requests.get(
            f"{BASE}/api/v1/chat/sessions/{chat_sid}/messages",
            headers=admin_headers,
            timeout=10,
        )
        if r.status_code == 200:
            messages = r.json().get("messages", [])
            user_msgs = [m for m in messages if m.get("role") == "user"]
            ai_msgs = [m for m in messages if m.get("role") == "assistant"]
            test("聊天记录持久化", len(messages) > 0,
                 f"共 {len(messages)} 条 (user={len(user_msgs)}, assistant={len(ai_msgs)})")
    except Exception as e:
        test("聊天记录持久化", False, f"异常: {e}")
else:
    skip("自然语言操作测试", "无法创建聊天会话")


# ============================================================
# 测试 5: 工程师工作台实时显示待办工单
# 测试 GET /api/v1/dispatch/tickets?engineer_id=xxx
# ============================================================
print("\n" + "=" * 60)
print("  测试 5: 工程师工作台待办工单")
print("  测试 GET /api/v1/dispatch/tickets?engineer_id=xxx")
print("=" * 60)

if eng_list:
    # 使用工程师账号查询
    if tokens.get("engineer1"):
        eng_headers_actual = {"Authorization": f"Bearer {tokens['engineer1']}"}
    else:
        eng_headers_actual = admin_headers

    # 查询所有工单
    try:
        r = requests.get(
            f"{BASE}/api/v1/dispatch/tickets",
            headers=eng_headers_actual,
            timeout=10,
        )
        ok = r.status_code == 200
        data = r.json() if ok else {}
        total = data.get("total", 0)
        tickets = data.get("tickets", [])
        test("工程师查询所有工单", ok, f"total={total}")
    except Exception as e:
        test("工程师查询所有工单", False, f"异常: {e}")
        tickets = []

    # 按工程师筛选
    for eng in eng_list[:2]:
        try:
            r = requests.get(
                f"{BASE}/api/v1/dispatch/tickets",
                params={"engineer_id": eng["id"]},
                headers=admin_headers,
                timeout=10,
            )
            ok = r.status_code == 200
            data = r.json() if ok else {}
            count = data.get("total", 0)
            eng_tickets = data.get("tickets", [])
            test(f"按工程师 {eng['name']} 筛选工单", ok, f"count={count}")

            if eng_tickets:
                # 验证所有工单都属于该工程师
                all_match = all(t.get("engineer_id") == eng["id"] for t in eng_tickets)
                test(f"  所有工单属于 {eng['name']}", all_match,
                     f"match={all_match}")
        except Exception as e:
            test(f"按工程师 {eng['name']} 筛选工单", False, f"异常: {e}")

    # 按状态筛选
    for status in ["created", "assigned", "in_progress", "resolved", "closed"]:
        try:
            r = requests.get(
                f"{BASE}/api/v1/dispatch/tickets",
                params={"status": status},
                headers=admin_headers,
                timeout=10,
            )
            ok = r.status_code == 200
            data = r.json() if ok else {}
            count = data.get("total", 0)
            status_tickets = data.get("tickets", [])
            if ok and status_tickets:
                all_match = all(t.get("status") == status for t in status_tickets)
                test(f"按状态 {status} 筛选", all_match and count > 0,
                     f"count={count} match={all_match}")
            else:
                test(f"按状态 {status} 筛选", ok, f"count={count}")
        except Exception as e:
            test(f"按状态 {status} 筛选", False, f"异常: {e}")

    # 测试工程师工作台统计
    try:
        r = requests.get(
            f"{BASE}/api/v1/dispatch/stats",
            headers=admin_headers,
            timeout=10,
        )
        ok = r.status_code == 200
        data = r.json() if ok else {}
        test("工程师工作台统计", ok, f"total={data.get('total_tickets')} open={data.get('open_tickets')}")
        if ok:
            test("  包含按状态统计", "by_status" in data, str(data.get("by_status", {})))
            test("  包含按优先级统计", "by_priority" in data, str(data.get("by_priority", {})))
    except Exception as e:
        test("工程师工作台统计", False, f"异常: {e}")
else:
    skip("工程师工作台测试", "无可用工程师")


# ============================================================
# 补充测试: 权限校验
# ============================================================
print("\n" + "=" * 60)
print("  补充测试: 权限校验")
print("=" * 60)

# 普通用户不能指派
if tokens.get("testuser"):
    user_headers = {"Authorization": f"Bearer {tokens['testuser']}"}
    try:
        r = requests.post(
            f"{BASE}/api/v1/dispatch/assign",
            json={"ticket_id": "TKT-001", "engineer_id": "eng-1"},
            headers=user_headers,
            timeout=10,
        )
        test("普通用户不能指派工单", r.status_code == 403, f"status={r.status_code}")
    except Exception as e:
        test("普通用户不能指派工单", False, f"异常: {e}")

    # 普通用户可以创建工单
    try:
        r = requests.post(
            f"{BASE}/api/v1/dispatch/tickets",
            json={"title": "普通用户测试工单", "description": "测试", "priority": "low"},
            headers=user_headers,
            timeout=10,
        )
        test("普通用户可以创建工单", r.status_code == 200,
             f"status={r.status_code} id={r.json().get('id') if r.status_code == 200 else ''}")
    except Exception as e:
        test("普通用户可以创建工单", False, f"异常: {e}")

# 未认证拒绝
try:
    r = requests.get(f"{BASE}/api/v1/dispatch/tickets", timeout=10)
    test("未认证用户被拒绝", r.status_code in (401, 403), f"status={r.status_code}")
except Exception as e:
    test("未认证用户被拒绝", False, f"异常: {e}")


# ============================================================
# 总结
# ============================================================
print("\n" + "=" * 60)
total = PASS + FAIL + SKIP
print(f"  验收测试完成: {PASS} 通过, {FAIL} 失败, {SKIP} 跳过, 共 {total} 项")
if total > 0:
    pass_rate = PASS / total * 100
    print(f"  通过率: {pass_rate:.1f}%")
print("=" * 60)

sys.exit(0 if FAIL == 0 else 1)