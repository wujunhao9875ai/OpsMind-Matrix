import pytest
import asyncio
from app.config import settings


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for each test case."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def sample_event():
    """Sample event data for testing."""
    return {
        "event_id": "evt-test-001",
        "source_agent": "test-agent",
        "event_type": "conversation",
        "trace_id": "trace-test-001",
        "user_id": "user-001",
        "payload": {"question": "测试问题", "answer": "测试答案"},
        "metadata": {"version": "1.0"},
    }


@pytest.fixture
def sample_material():
    """Sample material data for testing."""
    return {
        "question": "如何重启服务器？",
        "answer": "使用 systemctl restart 命令或 reboot 命令重启服务器。",
        "material_type": "qa_pair",
        "tags": ["运维", "服务器"],
        "difficulty": "easy",
    }


@pytest.fixture
def sample_dataset_request():
    """Sample dataset export request for testing."""
    return {
        "dataset_type": "qa",
        "format": "jsonl",
        "split": "train",
        "size": 100,
    }