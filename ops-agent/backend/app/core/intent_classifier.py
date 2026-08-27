import re
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import INTENT_CLASSIFY_PROMPT

# 关键词规则表（按顺序匹配：check_progress > repair > consult）
INTENT_RULES = {
    "check_progress": ["进度", "修好了吗", "工单状态", "什么时候", "处理了吗", "查一下", "到哪了"],
    "repair": ["坏了", "不能用", "报修", "故障", "出问题", "不工作", "坏掉", "卡住", "卡纸", "错误", "报错", "死机", "蓝屏", "黑屏", "连不上", "打不开", "开不了", "没反应", "不好使", "失灵", "异常", "崩溃", "闪退", "死机了", "开不了机", "不亮", "花屏", "重启", "自动关机", "没声音", "连不了网", "上不了网", "需要协助", "需要人", "来看", "来看下", "看下", "帮我", "帮忙", "修一下", "报修一下", "生成工单", "创建工单", "提交工单", "帮我报修", "需要报修", "帮我看看", "帮我查查", "无法使用", "无法打印", "无法工作", "无法解决", "解决不了", "处理不了", "搞不定", "弄不好", "不会修", "不会弄", "不会处理", "让人来", "派人来", "上门", "来一下", "过来看看", "来看看", "修不好", "没好", "还是不行", "还是没用", "还是坏的", "还是有问题", "没法用", "没法修", "叫人来", "帮我修", "帮我处理", "帮我弄", "帮我解决", "修理", "维修", "派个人", "找人来", "来人修", "上门修", "派人修", "报修吧", "工单吧", "提交吧", "叫人", "派人", "来修", "上门服务", "现场处理", "现场支持", "人工处理", "人工服务"],
    "consult": ["怎么", "如何", "为什么", "是什么", "在哪里", "设置", "操作", "步骤", "方法", "区别", "错误代码", "错误信息", "解决方案", "教程", "指南", "说明", "文档", "原因", "措施", "建议", "有没有", "是否", "能不能", "行不行", "可以吗", "怎么弄", "咋办", "哪里有", "在哪", "什么情况", "什么原因", "怎么回事", "什么办法", "该怎么办", "怎么处理", "怎么解决", "怎么弄好", "怎么做", "怎么设置", "怎么办", "排查", "诊断", "修复方法", "更新驱动", "升级驱动", "配置", "安装", "卸载", "备份", "恢复", "更新", "升级", "调节", "调整", "优化", "参数", "规格", "型号", "功能", "介绍", "简介", "概述", "支持", "驱动", "驱动下载", "IP地址", "地址", "端口", "默认", "兼容", "适配", "wifi", "WiFi", "wifi密码", "忘记密码", "重置密码", "改密码", "脱机", "离线", "连接不上", "无法连接", "密码错误", "网络", "连接", "慢", "卡顿", "慢了", "很慢", "太慢", "变慢", "打印", "打印质量", "打印效果", "打印不清晰", "硒鼓", "感光鼓", "墨盒", "碳粉", "模糊", "条纹", "黑线", "空白", "漏墨", "颜色", "彩色", "黑白"],
}


def classify_by_rules(message: str) -> str | None:
    """基于关键词规则匹配意图。"""
    msg_lower = message.lower()
    for intent, keywords in INTENT_RULES.items():
        for kw in keywords:
            if kw in msg_lower:
                return intent
    return None


def classify_by_model(message: str) -> str:
    """使用小模型兜底分类。"""
    prompt = INTENT_CLASSIFY_PROMPT.format(message=message)
    response = llm_adapter.chat_model.invoke(prompt)
    result = response.content.strip().lower()
    if result in ("repair", "consult", "check_progress"):
        return result
    return "consult"  # 默认按咨询处理


def classify_intent(message: str) -> str:
    """意图分类：先规则，规则未命中则用小模型兜底。"""
    rule_result = classify_by_rules(message)
    if rule_result:
        return rule_result
    # 规则未命中时，用小模型兜底分类
    try:
        return classify_by_model(message)
    except Exception:
        return "consult"