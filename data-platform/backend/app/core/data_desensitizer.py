"""数据脱敏 - 对敏感字段进行脱敏处理"""
import re
from app.core.logger import setup_logger

logger = setup_logger("data_desensitizer")

# Patterns for sensitive data
PHONE_PATTERN = re.compile(r'\b1[3-9]\d{9}\b')
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
ID_CARD_PATTERN = re.compile(r'\b\d{17}[\dXx]\b')
IP_PATTERN = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')


def desensitize_text(text: str) -> str:
    """Desensitize phone numbers, emails, ID cards, and IPs in text."""
    if not text:
        return text
    text = PHONE_PATTERN.sub(lambda m: m.group()[:3] + "****" + m.group()[-4:], text)
    text = EMAIL_PATTERN.sub(lambda m: m.group()[0] + "***@" + m.group().split("@")[1], text)
    text = ID_CARD_PATTERN.sub(lambda m: m.group()[:6] + "********" + m.group()[-4:], text)
    text = IP_PATTERN.sub(lambda m: ".".join(m.group().split(".")[:2]) + ".*.*", text)
    return text


def desensitize_event(event: dict) -> dict:
    """Desensitize sensitive fields in an event payload."""
    if "payload" in event and event["payload"]:
        if isinstance(event["payload"], dict):
            for key, value in event["payload"].items():
                if isinstance(value, str):
                    event["payload"][key] = desensitize_text(value)
        elif isinstance(event["payload"], str):
            event["payload"] = desensitize_text(event["payload"])
    return event