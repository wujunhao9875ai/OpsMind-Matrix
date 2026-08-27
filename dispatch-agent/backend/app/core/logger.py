import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": "dispatch-agent",
            "event": getattr(record, "event", record.msg),
            "session_id": getattr(record, "session_id", None),
            "user_id": getattr(record, "user_id", None),
            "duration_ms": getattr(record, "duration_ms", None),
            "query": getattr(record, "query", None),
            "result_count": getattr(record, "result_count", None),
            "top_score": getattr(record, "top_score", None),
            "error": getattr(record, "error", None),
        }
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
    return logger


def log_event(
    logger: logging.Logger,
    event: str,
    level: str = "INFO",
    session_id: str | None = None,
    user_id: str | None = None,
    duration_ms: float | None = None,
    **kwargs,
):
    sanitized = {}
    for key, value in kwargs.items():
        if isinstance(value, str) and len(value) > 200:
            sanitized[key] = value[:200] + "..."
        else:
            sanitized[key] = value
    extra = {"event": event, "session_id": session_id, "user_id": user_id, "duration_ms": duration_ms, **sanitized}
    logger.log(getattr(logging, level), event, extra=extra)