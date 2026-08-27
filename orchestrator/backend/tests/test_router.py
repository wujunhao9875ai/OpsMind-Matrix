"""路由测试"""
import pytest
from app.core.router import route_intent, clear_session_intent


def test_route_repair_intent():
    result = route_intent("打印机坏了，帮我报修")
    assert result["intent"] == "repair"
    assert result["target_agent"] == "dispatch-agent"


def test_route_explicit_repair_printer():
    """回归测试：用户明确报修打印机（带症状描述），应识别为 repair 并路由到 dispatch-agent"""
    result = route_intent("帮我报修一台打印机，打印模糊")
    assert result["intent"] == "repair"
    assert result["target_agent"] == "dispatch-agent"


def test_route_confirm_keeps_repair_session():
    """回归测试：报修会话中用户回复「需要」，应保持 repair 意图而非回落为 consult"""
    sid = "test-session-confirm-repair"
    clear_session_intent(sid)
    route_intent("帮我报修一台打印机，打印模糊", session_id=sid)
    result = route_intent("需要", session_id=sid)
    assert result["intent"] == "repair"
    assert result["target_agent"] == "dispatch-agent"
    clear_session_intent(sid)


def test_route_consult_intent():
    result = route_intent("怎么设置打印机？")
    assert result["intent"] == "consult"
    assert result["target_agent"] == "ops-agent"


def test_route_check_progress_intent():
    result = route_intent("查一下我的工单进度")
    assert result["intent"] == "check_progress"
    assert result["target_agent"] == "dispatch-agent"


def test_route_ticket_no_query():
    """回归测试：输入工单编号应识别为 check_progress 并路由到 dispatch-agent"""
    result = route_intent("WO-20260827-9316")
    assert result["intent"] == "check_progress"
    assert result["target_agent"] == "dispatch-agent"


def test_route_query_ticket_phrase():
    """回归测试：查询工单/我的工单相关表述应路由到 dispatch-agent"""
    for msg in ["查询工单", "查询工单WO-20260827-9316", "我的工单"]:
        result = route_intent(msg)
        assert result["intent"] == "check_progress", msg
        assert result["target_agent"] == "dispatch-agent", msg


def test_route_ticket_no_overrides_repair_session():
    """回归测试：报修会话结束后查询工单编号，应路由到 dispatch-agent 而非 repair"""
    sid = "test-session-query-after-repair"
    clear_session_intent(sid)
    route_intent("帮我报修一台打印机，打印模糊", session_id=sid)
    result = route_intent("WO-20260827-9316", session_id=sid)
    assert result["intent"] == "check_progress"
    assert result["target_agent"] == "dispatch-agent"
    clear_session_intent(sid)


def test_route_warehouse_intent():
    result = route_intent("我要入库一台设备")
    assert result["intent"] == "warehouse_op"
    assert result["target_agent"] == "warehouse-agent"


def test_route_spare_request_intent():
    result = route_intent("需要更换备件")
    assert result["intent"] == "spare_request"
    assert result["target_agent"] == "dispatch-agent"


def test_route_query_stats_intent():
    result = route_intent("本周的统计报表")
    assert result["intent"] == "query_stats"
    assert result["target_agent"] == "dispatch-agent"


def test_route_data_query_intent():
    result = route_intent("导出数据集到数据中台")
    assert result["intent"] == "data_query"
    assert result["target_agent"] == "data-platform"


def test_route_ticket_manage_intent():
    result = route_intent("把这个工单转给张三")
    assert result["intent"] == "ticket_manage"
    assert result["target_agent"] == "dispatch-agent"


def test_route_default_to_consult():
    result = route_intent("你好")
    assert result["intent"] == "consult"
    assert result["target_agent"] == "ops-agent"