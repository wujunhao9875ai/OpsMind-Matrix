import json
import logging
import sys
from datetime import datetime, timezone


def setup_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(handler)
    return logger


def log_event(logger, event: str, trace_id: str = None, **kwargs):
    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": "INFO",
        "service": "ops-agent",
        "event": event,
    }
    if trace_id:
        log_data["traceId"] = trace_id
    log_data.update(kwargs)
    logger.info(json.dumps(log_data, ensure_ascii=False))