import pytest
from app.core.intent_classifier import classify_intent, classify_by_rules


def test_classify_repair_by_rules():
    """测试规则匹配报修意图。"""
    assert classify_by_rules("打印机坏了") == "repair"
    assert classify_by_rules("电脑不能用") == "repair"
    assert classify_by_rules("帮我报修一下") == "repair"


def test_classify_consult_by_rules():
    """测试规则匹配咨询意图。"""
    assert classify_by_rules("怎么连接打印机") == "consult"
    assert classify_by_rules("如何设置网络") == "consult"


def test_classify_check_progress_by_rules():
    """测试规则匹配查进度意图。"""
    assert classify_by_rules("查一下工单进度") == "check_progress"


def test_classify_intent_fallback():
    """测试意图分类兜底。"""
    # 规则未命中时走模型兜底，但至少不会报错
    result = classify_intent("你好")
    assert result in ("repair", "consult", "check_progress")


def test_classify_intent_repair():
    """测试完整意图分类 - 报修。"""
    assert classify_intent("打印机坏了帮我修一下") == "repair"


def test_classify_intent_consult():
    """测试完整意图分类 - 咨询。"""
    assert classify_intent("怎么设置打印机") == "consult"