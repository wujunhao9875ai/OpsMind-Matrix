"""统一日志模块"""
import logging
import json
import sys
from datetime import datetime, timezone


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """Set up a logger with structured JSON output."""
    logger = logging.getLogger(name)
    logger.setLevel(level)

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            '{"timestamp":"%(asctime)s","logger":"%(name)s","level":"%(levelname)s","message":"%(message)s"}',
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger


def log_event(logger: logging.Logger, event: str, level: str = "INFO", **kwargs):
    """Log a structured event with additional context."""
    log_data = {"event": event, **kwargs}
    log_func = getattr(logger, level.lower(), logger.info)
    log_func(json.dumps(log_data, ensure_ascii=False))