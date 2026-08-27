"""traceId 生成与追踪"""
import uuid

def generate_trace_id() -> str:
    return str(uuid.uuid4())