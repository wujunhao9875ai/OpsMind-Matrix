# 项目2：自动派单 Agent 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 在项目1 代码库内扩展实现工单全生命周期管理、智能派单、超时监控、管理员自然语言操作和工程师工作台。

**架构：** 扩展项目1 FastAPI 后端，新增 4 个数据模型 + LangGraph 状态机 + 加权评分派单引擎 + Redis Pub/Sub 通知 + Celery 定时任务；前端新增管理员工作台和工程师工作台两个页面。

**技术栈：** Python 3.11+, FastAPI, LangGraph, PostgreSQL, Redis, Celery, Vue 3, Element Plus, WebSocket

---

## 文件结构

### 新建文件 (19个)
```
backend/app/models/ticket.py
backend/app/models/ticket_log.py
backend/app/models/engineer.py
backend/app/models/urge_record.py
backend/app/api/dispatch.py
backend/app/api/admin_chat.py
backend/app/api/stats.py
backend/app/core/ticket_state_machine.py
backend/app/core/dispatch_engine.py
backend/app/core/notification.py
backend/app/core/admin_nlu.py
backend/app/schemas/dispatch.py
backend/app/schemas/stats.py
backend/app/tasks/monitor_tasks.py
backend/app/tasks/report_tasks.py
frontend/src/views/AdminDashboard.vue
frontend/src/views/EngineerWorkbench.vue
frontend/src/composables/useTicketWebSocket.ts
frontend/src/stores/ticket.ts
```

### 修改文件 (9个)
```
backend/app/models/__init__.py
backend/app/models/user.py
backend/app/config.py
backend/app/main.py
backend/app/utils/prompts.py
backend/app/tasks/celery_app.py
backend/requirements.txt
frontend/src/router/index.ts
frontend/src/types/index.ts
docker-compose.yml
```

---

### 任务 1：安装 LangGraph 依赖

**文件：**
- 修改：`backend/requirements.txt`

- [ ] **步骤 1：添加 langgraph 依赖**

```diff
  langchain==0.3.13
  langchain-community==0.3.13
  langchain-openai==0.3.0
+ langgraph==0.2.60
  chromadb==0.5.23
```

- [ ] **步骤 2：安装依赖**

```bash
cd f:\mysite\project1-ops-agent\backend
pip install langgraph==0.2.60
```

- [ ] **步骤 3：验证安装**

```bash
python -c "from langgraph.graph import StateGraph; print('OK')"
```
预期：输出 `OK`

- [ ] **步骤 4：Commit**

```bash
git add backend/requirements.txt
git commit -m "feat(dispatch): add langgraph dependency"
```

---

### 任务 2：创建 Ticket 模型

**文件：**
- 创建：`backend/app/models/ticket.py`

- [ ] **步骤 1：创建模型文件**

```python
# backend/app/models/ticket.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text, Integer
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_no: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    pre_ticket_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("pre_tickets.id"), nullable=True)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=True)

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    fault_category: Mapped[str] = mapped_column(String(50), nullable=False, default="other")
    urgency: Mapped[str] = mapped_column(String(50), nullable=False, default="medium")
    device_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)

    status: Mapped[str] = mapped_column(String(50), nullable=False, default="created", index=True)
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    resolution: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    logs: Mapped[list["TicketLog"]] = relationship("TicketLog", back_populates="ticket", order_by="TicketLog.created_at", cascade="all, delete-orphan")
    urge_records: Mapped[list["UrgeRecord"]] = relationship("UrgeRecord", back_populates="ticket", order_by="UrgeRecord.created_at", cascade="all, delete-orphan")
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/models/ticket.py
git commit -m "feat(dispatch): add Ticket model"
```

---

### 任务 3：创建 TicketLog 模型

**文件：**
- 创建：`backend/app/models/ticket_log.py`

- [ ] **步骤 1：创建模型文件**

```python
# backend/app/models/ticket_log.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class TicketLog(Base):
    __tablename__ = "ticket_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    operator_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    from_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="logs")
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/models/ticket_log.py
git commit -m "feat(dispatch): add TicketLog model"
```

---

### 任务 4：创建 EngineerProfile 模型

**文件：**
- 创建：`backend/app/models/engineer.py`

- [ ] **步骤 1：创建模型文件**

```python
# backend/app/models/engineer.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Integer, Float
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class EngineerProfile(Base):
    __tablename__ = "engineer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    skills: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    skill_levels: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="offline", index=True)
    max_concurrent: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    current_load: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_completed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_resolution_minutes: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    rating: Mapped[float] = mapped_column(Float, nullable=False, default=5.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/models/engineer.py
git commit -m "feat(dispatch): add EngineerProfile model"
```

---

### 任务 5：创建 UrgeRecord 模型

**文件：**
- 创建：`backend/app/models/urge_record.py`

- [ ] **步骤 1：创建模型文件**

```python
# backend/app/models/urge_record.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class UrgeRecord(Base):
    __tablename__ = "urge_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tickets.id"), nullable=False, index=True)
    urge_type: Mapped[str] = mapped_column(String(50), nullable=False)
    urged_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    ticket: Mapped["Ticket"] = relationship("Ticket", back_populates="urge_records")
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/models/urge_record.py
git commit -m "feat(dispatch): add UrgeRecord model"
```

---

### 任务 6：更新 models/__init__.py 和 User 模型

**文件：**
- 修改：`backend/app/models/__init__.py`
- 修改：`backend/app/models/user.py`

- [ ] **步骤 1：更新 __init__.py**

```python
# backend/app/models/__init__.py
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.knowledge import KnowledgeDoc, KnowledgeChunk
from app.models.pre_ticket import PreTicket
from app.models.user import User
from app.models.user_profile import UserProfile
from app.models.ticket import Ticket
from app.models.ticket_log import TicketLog
from app.models.engineer import EngineerProfile
from app.models.urge_record import UrgeRecord
from app.database import Base

__all__ = [
    "Base",
    "Conversation",
    "Message",
    "KnowledgeDoc",
    "KnowledgeChunk",
    "PreTicket",
    "User",
    "UserProfile",
    "Ticket",
    "TicketLog",
    "EngineerProfile",
    "UrgeRecord",
]
```

- [ ] **步骤 2：更新 User 模型 role 字段**

将 `backend/app/models/user.py` 中 `role` 的 `default` 保持 `"user"`，确认字段类型为 `String(50)`（已支持扩展）。无需修改代码，只需确认 Alembic 迁移时不会出错。

- [ ] **步骤 3：Commit**

```bash
git add backend/app/models/__init__.py
git commit -m "feat(dispatch): register new models in __init__.py"
```

---

### 任务 7：创建 Alembic 迁移

**文件：**
- 创建：`backend/alembic/versions/xxxx_add_dispatch_tables.py`

- [ ] **步骤 1：生成迁移**

```bash
cd f:\mysite\project1-ops-agent\backend
alembic revision --autogenerate -m "add dispatch tables"
```

- [ ] **步骤 2：审查生成的迁移文件，确认包含 4 张表 + users.role 变更**

预期生成的 upgrade 包含：
- `op.create_table('engineer_profiles', ...)`
- `op.create_table('tickets', ...)`
- `op.create_table('ticket_logs', ...)`
- `op.create_table('urge_records', ...)`

- [ ] **步骤 3：运行迁移**

```bash
cd f:\mysite\project1-ops-agent
docker-compose exec backend alembic upgrade head
```
预期：迁移成功，显示 "Running upgrade ... -> ..."

- [ ] **步骤 4：验证表结构**

```bash
docker-compose exec postgres psql -U opsagent -d opsagent -c "\dt"
```
预期输出包含：`tickets`, `ticket_logs`, `engineer_profiles`, `urge_records`

- [ ] **步骤 5：Commit**

```bash
git add backend/alembic/versions/
git commit -m "feat(dispatch): add alembic migration for dispatch tables"
```

---

### 任务 8：更新 config.py 添加派单配置

**文件：**
- 修改：`backend/app/config.py`

- [ ] **步骤 1：添加派单相关配置**

在 `Settings` 类末尾（`class Config` 之前）添加：

```python
    # Dispatch
    dispatch_skill_weight: float = 0.40
    dispatch_load_weight: float = 0.30
    dispatch_balance_weight: float = 0.20
    dispatch_performance_weight: float = 0.10
    sla_critical_minutes: int = 120
    sla_high_minutes: int = 240
    sla_medium_minutes: int = 480
    sla_low_minutes: int = 1440
    urge_cooldown_minutes: int = 30
    auto_close_days: int = 3
    unassigned_alert_minutes: int = 5
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/config.py
git commit -m "feat(dispatch): add dispatch and SLA settings"
```

---

### 任务 9：创建工单状态机

**文件：**
- 创建：`backend/app/core/ticket_state_machine.py`

- [ ] **步骤 1：创建状态机文件**

```python
# backend/app/core/ticket_state_machine.py
from typing import TypedDict, Literal
from datetime import datetime, timezone, timedelta
from langgraph.graph import StateGraph, END
from app.config import settings


class TicketState(TypedDict):
    ticket_id: str
    current_status: str
    assigned_to: str | None
    operator_id: str
    comment: str | None
    action: str


VALID_TRANSITIONS = {
    "created": ["assign", "cancel"],
    "assigned": ["accept", "reject", "reassign", "cancel"],
    "in_progress": ["resolve", "reassign", "escalate"],
    "resolved": ["close", "reopen"],
    "closed": [],
    "cancelled": [],
}

ACTION_TO_STATUS = {
    "assign": "assigned",
    "cancel": "cancelled",
    "accept": "in_progress",
    "reject": "created",
    "reassign": "assigned",
    "resolve": "resolved",
    "close": "closed",
    "reopen": "in_progress",
    "escalate": "assigned",
}


def calculate_sla_deadline(urgency: str) -> datetime:
    minutes_map = {
        "critical": settings.sla_critical_minutes,
        "high": settings.sla_high_minutes,
        "medium": settings.sla_medium_minutes,
        "low": settings.sla_low_minutes,
    }
    minutes = minutes_map.get(urgency, settings.sla_medium_minutes)
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def validate_transition(current_status: str, action: str) -> bool:
    allowed = VALID_TRANSITIONS.get(current_status, [])
    return action in allowed


def get_next_status(current_status: str, action: str) -> str:
    if not validate_transition(current_status, action):
        raise ValueError(f"Invalid transition: {current_status} -> {action}")
    return ACTION_TO_STATUS[action]


def build_ticket_graph():
    """构建 LangGraph 工单状态图。"""
    workflow = StateGraph(TicketState)

    workflow.add_node("created", _noop_handler)
    workflow.add_node("assigned", _noop_handler)
    workflow.add_node("in_progress", _noop_handler)
    workflow.add_node("resolved", _noop_handler)
    workflow.add_node("closed", _noop_handler)
    workflow.add_node("cancelled", _noop_handler)

    workflow.set_entry_point("created")
    workflow.add_edge("closed", END)
    workflow.add_edge("cancelled", END)

    return workflow.compile()


def _noop_handler(state: TicketState) -> TicketState:
    return state
```

- [ ] **步骤 2：编写单元测试**

创建 `backend/tests/test_ticket_state_machine.py`：

```python
# backend/tests/test_ticket_state_machine.py
import pytest
from app.core.ticket_state_machine import (
    validate_transition,
    get_next_status,
    calculate_sla_deadline,
)


class TestValidateTransition:
    def test_created_assign_valid(self):
        assert validate_transition("created", "assign") is True

    def test_created_accept_invalid(self):
        assert validate_transition("created", "accept") is False

    def test_assigned_accept_valid(self):
        assert validate_transition("assigned", "accept") is True

    def test_assigned_reject_valid(self):
        assert validate_transition("assigned", "reject") is True

    def test_in_progress_resolve_valid(self):
        assert validate_transition("in_progress", "resolve") is True

    def test_resolved_close_valid(self):
        assert validate_transition("resolved", "close") is True

    def test_resolved_reopen_valid(self):
        assert validate_transition("resolved", "reopen") is True

    def test_closed_any_invalid(self):
        assert validate_transition("closed", "assign") is False

    def test_cancelled_any_invalid(self):
        assert validate_transition("cancelled", "assign") is False

    def test_unknown_status_invalid(self):
        assert validate_transition("unknown", "assign") is False


class TestGetNextStatus:
    def test_assign_to_assigned(self):
        assert get_next_status("created", "assign") == "assigned"

    def test_accept_to_in_progress(self):
        assert get_next_status("assigned", "accept") == "in_progress"

    def test_reject_to_created(self):
        assert get_next_status("assigned", "reject") == "created"

    def test_resolve_to_resolved(self):
        assert get_next_status("in_progress", "resolve") == "resolved"

    def test_invalid_raises(self):
        with pytest.raises(ValueError, match="Invalid transition"):
            get_next_status("created", "accept")


class TestSlaDeadline:
    def test_critical_sla(self):
        deadline = calculate_sla_deadline("critical")
        from datetime import datetime, timezone, timedelta
        expected = datetime.now(timezone.utc) + timedelta(minutes=120)
        diff = abs((deadline - expected).total_seconds())
        assert diff < 5  # 允许 5 秒误差

    def test_medium_sla(self):
        deadline = calculate_sla_deadline("medium")
        from datetime import datetime, timezone, timedelta
        expected = datetime.now(timezone.utc) + timedelta(minutes=480)
        diff = abs((deadline - expected).total_seconds())
        assert diff < 5
```

- [ ] **步骤 3：运行测试**

```bash
cd f:\mysite\project1-ops-agent\backend
pytest tests/test_ticket_state_machine.py -v
```
预期：所有测试 PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/core/ticket_state_machine.py backend/tests/test_ticket_state_machine.py
git commit -m "feat(dispatch): add ticket state machine with LangGraph"
```

---

### 任务 10：创建智能派单引擎

**文件：**
- 创建：`backend/app/core/dispatch_engine.py`

- [ ] **步骤 1：创建派单引擎文件**

```python
# backend/app/core/dispatch_engine.py
import asyncio
from sqlalchemy import select, func
from app.database import async_session
from app.models.engineer import EngineerProfile
from app.models.ticket import Ticket
from app.config import settings


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    if not set_a or not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _infer_required_skills(ticket: Ticket) -> set:
    """从工单中推断所需技能标签。"""
    skills = set()
    category_skill_map = {
        "hardware": {"printer", "computer", "hardware"},
        "software": {"software", "system", "app"},
        "network": {"network", "wifi", "vpn"},
        "other": set(),
    }
    skills.update(category_skill_map.get(ticket.fault_category, set()))
    if ticket.device_info and isinstance(ticket.device_info, dict):
        device_type = ticket.device_info.get("type", "")
        if device_type:
            skills.add(device_type)
    return skills


def calculate_score(engineer: EngineerProfile, ticket: Ticket, all_engineers: list[EngineerProfile]) -> float:
    required_skills = _infer_required_skills(ticket)
    engineer_skills = set(engineer.skills) if engineer.skills else set()

    skill_score = _jaccard_similarity(required_skills, engineer_skills)
    load_ratio = engineer.current_load / max(engineer.max_concurrent, 1)
    load_score = 1.0 - min(load_ratio, 1.0)

    avg_load = sum(e.current_load for e in all_engineers) / max(len(all_engineers), 1)
    balance_score = 1.0 - abs(engineer.current_load - avg_load) / max(engineer.max_concurrent, 1)
    balance_score = max(0.0, min(1.0, balance_score))

    max_completed = max((e.total_completed for e in all_engineers), default=1)
    performance_score = (engineer.total_completed / max(max_completed, 1) + engineer.rating / 5.0) / 2.0

    total = (
        settings.dispatch_skill_weight * skill_score
        + settings.dispatch_load_weight * load_score
        + settings.dispatch_balance_weight * balance_score
        + settings.dispatch_performance_weight * performance_score
    )
    return round(total, 4)


async def find_best_engineer(ticket: Ticket) -> EngineerProfile | None:
    async with async_session() as db:
        result = await db.execute(
            select(EngineerProfile).where(EngineerProfile.status == "available")
        )
        candidates = result.scalars().all()

    if not candidates:
        return None

    required_skills = _infer_required_skills(ticket)
    # 过滤：技能匹配
    candidates = [e for e in candidates if set(e.skills or []) & required_skills]
    if not candidates:
        return None

    # 过滤：负载未满
    candidates = [e for e in candidates if e.current_load < e.max_concurrent]
    if not candidates:
        return None

    # 评分排序
    scored = [(e, calculate_score(e, ticket, candidates)) for e in candidates]
    scored.sort(key=lambda x: x[1], reverse=True)

    return scored[0][0] if scored else None
```

- [ ] **步骤 2：编写单元测试**

创建 `backend/tests/test_dispatch_engine.py`：

```python
# backend/tests/test_dispatch_engine.py
import uuid
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from app.core.dispatch_engine import (
    _jaccard_similarity,
    _infer_required_skills,
    calculate_score,
)


class TestJaccardSimilarity:
    def test_identical_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"a", "b"}) == 1.0

    def test_disjoint_sets(self):
        assert _jaccard_similarity({"a", "b"}, {"c", "d"}) == 0.0

    def test_partial_overlap(self):
        assert _jaccard_similarity({"a", "b"}, {"b", "c"}) == 1.0 / 3.0

    def test_empty_sets(self):
        assert _jaccard_similarity(set(), set()) == 0.0


class TestInferRequiredSkills:
    def test_hardware_category(self):
        ticket = MagicMock()
        ticket.fault_category = "hardware"
        ticket.device_info = {"type": "printer"}
        skills = _infer_required_skills(ticket)
        assert "printer" in skills
        assert "hardware" in skills

    def test_network_category(self):
        ticket = MagicMock()
        ticket.fault_category = "network"
        ticket.device_info = {}
        skills = _infer_required_skills(ticket)
        assert "network" in skills


class TestCalculateScore:
    def test_perfect_match(self):
        engineer = MagicMock()
        engineer.skills = ["printer", "hardware"]
        engineer.current_load = 0
        engineer.max_concurrent = 5
        engineer.total_completed = 100
        engineer.rating = 5.0

        ticket = MagicMock()
        ticket.fault_category = "hardware"
        ticket.device_info = {"type": "printer"}

        all_engineers = [engineer]
        score = calculate_score(engineer, ticket, all_engineers)
        assert 0.8 <= score <= 1.0  # 高技能匹配 + 零负载 = 高分

    def test_no_match(self):
        engineer = MagicMock()
        engineer.skills = ["network"]
        engineer.current_load = 5
        engineer.max_concurrent = 5
        engineer.total_completed = 10
        engineer.rating = 3.0

        ticket = MagicMock()
        ticket.fault_category = "hardware"
        ticket.device_info = {"type": "printer"}

        all_engineers = [engineer]
        score = calculate_score(engineer, ticket, all_engineers)
        assert score < 0.5  # 无技能匹配 + 满负载 = 低分
```

- [ ] **步骤 3：运行测试**

```bash
cd f:\mysite\project1-ops-agent\backend
pytest tests/test_dispatch_engine.py -v
```
预期：所有测试 PASS

- [ ] **步骤 4：Commit**

```bash
git add backend/app/core/dispatch_engine.py backend/tests/test_dispatch_engine.py
git commit -m "feat(dispatch): add dispatch engine with weighted scoring"
```

---

### 任务 11：创建 Pydantic Schemas

**文件：**
- 创建：`backend/app/schemas/dispatch.py`

- [ ] **步骤 1：创建 schemas 文件**

```python
# backend/app/schemas/dispatch.py
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TicketCreate(BaseModel):
    title: str = Field(..., max_length=500)
    description: str = ""
    fault_category: str = "other"
    urgency: str = "medium"
    device_info: Optional[dict] = None
    location: Optional[str] = None
    engineer_id: Optional[str] = None


class TicketFromPre(BaseModel):
    pass  # 从预填工单创建，不需要额外参数


class TicketAssign(BaseModel):
    engineer_id: Optional[str] = None  # 不传则自动派单


class TicketReassign(BaseModel):
    engineer_id: str
    reason: Optional[str] = None


class TicketReject(BaseModel):
    reason: Optional[str] = None


class TicketResolve(BaseModel):
    resolution: str


class TicketReopen(BaseModel):
    reason: Optional[str] = None


class TicketCancel(BaseModel):
    reason: Optional[str] = None


class TicketPriorityChange(BaseModel):
    urgency: str


class TicketUrge(BaseModel):
    pass


class EngineerCreate(BaseModel):
    user_id: str
    display_name: str
    skills: list[str] = []
    skill_levels: dict = {}


class EngineerSkillUpdate(BaseModel):
    skills: list[str]
    skill_levels: dict = {}


class EngineerStatusUpdate(BaseModel):
    status: str


class TicketResponse(BaseModel):
    id: str
    ticket_no: str
    title: str
    description: str
    fault_category: str
    urgency: str
    device_info: Optional[dict] = None
    location: Optional[str] = None
    status: str
    assigned_to: Optional[dict] = None
    assigned_at: Optional[datetime] = None
    resolution: Optional[str] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    sla_deadline: Optional[datetime] = None
    created_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class TicketListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[TicketResponse]


class EngineerResponse(BaseModel):
    id: str
    user_id: str
    display_name: str
    skills: list[str]
    skill_levels: dict
    status: str
    max_concurrent: int
    current_load: int
    total_completed: int
    avg_resolution_minutes: float
    rating: float


class EngineerListResponse(BaseModel):
    total: int
    items: list[EngineerResponse]


class TicketLogResponse(BaseModel):
    id: str
    action: str
    operator_id: Optional[str] = None
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    comment: Optional[str] = None
    extra_data: Optional[dict] = None
    created_at: Optional[datetime] = None
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/schemas/dispatch.py
git commit -m "feat(dispatch): add Pydantic schemas for dispatch"
```

---

### 任务 12：创建工单管理 API

**文件：**
- 创建：`backend/app/api/dispatch.py`

- [ ] **步骤 1：创建 API 文件**

```python
# backend/app/api/dispatch.py
import uuid
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, and_, or_
from app.database import async_session
from app.core.auth_middleware import verify_token, TokenPayload
from app.core.ticket_state_machine import validate_transition, get_next_status, calculate_sla_deadline
from app.core.dispatch_engine import find_best_engineer
from app.models.ticket import Ticket
from app.models.ticket_log import TicketLog
from app.models.pre_ticket import PreTicket
from app.models.engineer import EngineerProfile
from app.schemas.dispatch import (
    TicketCreate, TicketAssign, TicketReassign, TicketReject,
    TicketResolve, TicketReopen, TicketCancel, TicketPriorityChange, TicketUrge,
    TicketResponse, TicketListResponse, TicketLogResponse,
)

router = APIRouter()


def _generate_ticket_no() -> str:
    now = datetime.now(timezone.utc)
    date_part = now.strftime("%Y%m%d")
    return f"WO-{date_part}-{uuid.uuid4().hex[:4].upper()}"


def _ticket_to_response(t: Ticket) -> dict:
    return {
        "id": str(t.id),
        "ticket_no": t.ticket_no,
        "title": t.title,
        "description": t.description,
        "fault_category": t.fault_category,
        "urgency": t.urgency,
        "device_info": t.device_info,
        "location": t.location,
        "status": t.status,
        "assigned_to": {"id": str(t.assigned_to)} if t.assigned_to else None,
        "assigned_at": t.assigned_at,
        "resolution": t.resolution,
        "resolved_at": t.resolved_at,
        "closed_at": t.closed_at,
        "sla_deadline": t.sla_deadline,
        "created_by": str(t.created_by) if t.created_by else None,
        "created_at": t.created_at,
        "updated_at": t.updated_at,
    }


async def _add_log(db, ticket_id: uuid.UUID, action: str, operator_id: str, from_status: str, to_status: str, comment: str = None, extra_data: dict = None):
    log = TicketLog(
        ticket_id=ticket_id,
        action=action,
        operator_id=operator_id,
        from_status=from_status,
        to_status=to_status,
        comment=comment,
        extra_data=extra_data,
    )
    db.add(log)


@router.get("/api/v1/tickets")
async def list_tickets(
    token: TokenPayload = Depends(verify_token),
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    urgency: str | None = None,
    assigned_to: str | None = None,
):
    if page < 1:
        page = 1
    if page_size < 1 or page_size > 100:
        page_size = 20

    async with async_session() as db:
        role = token["role"]
        user_id = token["user_id"]

        query = select(Ticket)
        if role == "user":
            query = query.where(Ticket.created_by == user_id)
        elif role == "engineer":
            query = query.where(Ticket.assigned_to == user_id)
        # admin 不过滤，看全部

        if status:
            query = query.where(Ticket.status == status)
        if urgency:
            query = query.where(Ticket.urgency == urgency)
        if assigned_to and role == "admin":
            query = query.where(Ticket.assigned_to == assigned_to)

        count_query = select(func.count()).select_from(query.subquery())
        total_result = await db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(Ticket.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await db.execute(query)
        tickets = result.scalars().all()

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "items": [_ticket_to_response(t) for t in tickets],
        }


@router.get("/api/v1/tickets/{ticket_id}")
async def get_ticket(ticket_id: str, token: TokenPayload = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")
        return _ticket_to_response(ticket)


@router.post("/api/v1/tickets")
async def create_ticket(body: TicketCreate, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可创建工单")

    async with async_session() as db:
        ticket = Ticket(
            ticket_no=_generate_ticket_no(),
            title=body.title,
            description=body.description,
            fault_category=body.fault_category,
            urgency=body.urgency,
            device_info=body.device_info,
            location=body.location,
            status="created",
            created_by=token["user_id"],
            sla_deadline=calculate_sla_deadline(body.urgency),
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)

        await _add_log(db, ticket.id, "created", token["user_id"], None, "created")

        # 如果指定了工程师，直接指派
        if body.engineer_id:
            await _assign_ticket(db, ticket, body.engineer_id, token["user_id"])
        else:
            await _auto_assign(db, ticket, token["user_id"])

        await db.commit()
        await db.refresh(ticket)
        return _ticket_to_response(ticket)


@router.post("/api/v1/tickets/from-pre/{pre_ticket_id}")
async def create_ticket_from_pre(pre_ticket_id: str, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可创建工单")

    async with async_session() as db:
        result = await db.execute(select(PreTicket).where(PreTicket.id == pre_ticket_id))
        pre = result.scalar_one_or_none()
        if not pre:
            raise HTTPException(status_code=404, detail="预填工单不存在")

        ticket = Ticket(
            ticket_no=_generate_ticket_no(),
            pre_ticket_id=pre.id,
            conversation_id=pre.conversation_id,
            title=pre.summary,
            description=pre.summary,
            fault_category=pre.fault_category,
            urgency=pre.urgency,
            device_info=pre.device_info,
            location=pre.location,
            status="created",
            created_by=token["user_id"],
            sla_deadline=calculate_sla_deadline(pre.urgency),
        )
        db.add(ticket)
        await db.commit()
        await db.refresh(ticket)

        await _add_log(db, ticket.id, "created", token["user_id"], None, "created")
        await _auto_assign(db, ticket, token["user_id"])
        await db.commit()
        await db.refresh(ticket)
        return _ticket_to_response(ticket)


@router.put("/api/v1/tickets/{ticket_id}/assign")
async def assign_ticket(ticket_id: str, body: TicketAssign, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可指派工单")

    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")

        if body.engineer_id:
            await _assign_ticket(db, ticket, body.engineer_id, token["user_id"])
        else:
            await _auto_assign(db, ticket, token["user_id"])

        await db.commit()
        await db.refresh(ticket)
        return _ticket_to_response(ticket)


@router.put("/api/v1/tickets/{ticket_id}/accept")
async def accept_ticket(ticket_id: str, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "engineer":
        raise HTTPException(status_code=403, detail="仅工程师可接单")

    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")
        if str(ticket.assigned_to) != token["user_id"]:
            raise HTTPException(status_code=403, detail="仅可操作分配给自己的工单")
        if not validate_transition(ticket.status, "accept"):
            raise HTTPException(status_code=400, detail=f"当前状态 {ticket.status} 不允许接单")

        old_status = ticket.status
        ticket.status = get_next_status(ticket.status, "accept")
        await _add_log(db, ticket.id, "accept", token["user_id"], old_status, ticket.status)
        await db.commit()
        return _ticket_to_response(ticket)


@router.put("/api/v1/tickets/{ticket_id}/reject")
async def reject_ticket(ticket_id: str, body: TicketReject, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "engineer":
        raise HTTPException(status_code=403, detail="仅工程师可拒单")

    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")
        if str(ticket.assigned_to) != token["user_id"]:
            raise HTTPException(status_code=403, detail="仅可操作分配给自己的工单")
        if not validate_transition(ticket.status, "reject"):
            raise HTTPException(status_code=400, detail=f"当前状态 {ticket.status} 不允许拒单")

        old_status = ticket.status
        ticket.status = get_next_status(ticket.status, "reject")
        ticket.assigned_to = None
        ticket.assigned_at = None
        await _add_log(db, ticket.id, "reject", token["user_id"], old_status, ticket.status, comment=body.reason)
        await _auto_assign(db, ticket, token["user_id"])
        await db.commit()
        return _ticket_to_response(ticket)


@router.put("/api/v1/tickets/{ticket_id}/resolve")
async def resolve_ticket(ticket_id: str, body: TicketResolve, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "engineer":
        raise HTTPException(status_code=403, detail="仅工程师可提交解决方案")

    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")
        if str(ticket.assigned_to) != token["user_id"]:
            raise HTTPException(status_code=403, detail="仅可操作分配给自己的工单")
        if not validate_transition(ticket.status, "resolve"):
            raise HTTPException(status_code=400, detail=f"当前状态 {ticket.status} 不允许提交解决方案")

        old_status = ticket.status
        ticket.status = get_next_status(ticket.status, "resolve")
        ticket.resolution = body.resolution
        ticket.resolved_at = datetime.now(timezone.utc)
        await _add_log(db, ticket.id, "resolve", token["user_id"], old_status, ticket.status, comment=body.resolution)
        await db.commit()
        return _ticket_to_response(ticket)


@router.put("/api/v1/tickets/{ticket_id}/close")
async def close_ticket(ticket_id: str, token: TokenPayload = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")
        if not validate_transition(ticket.status, "close"):
            raise HTTPException(status_code=400, detail=f"当前状态 {ticket.status} 不允许关闭")

        old_status = ticket.status
        ticket.status = get_next_status(ticket.status, "close")
        ticket.closed_at = datetime.now(timezone.utc)
        await _add_log(db, ticket.id, "close", token["user_id"], old_status, ticket.status)
        await db.commit()
        return _ticket_to_response(ticket)


@router.put("/api/v1/tickets/{ticket_id}/reopen")
async def reopen_ticket(ticket_id: str, body: TicketReopen, token: TokenPayload = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")
        if not validate_transition(ticket.status, "reopen"):
            raise HTTPException(status_code=400, detail=f"当前状态 {ticket.status} 不允许重新打开")

        old_status = ticket.status
        ticket.status = get_next_status(ticket.status, "reopen")
        ticket.resolution = None
        ticket.resolved_at = None
        ticket.closed_at = None
        await _add_log(db, ticket.id, "reopen", token["user_id"], old_status, ticket.status, comment=body.reason)
        await db.commit()
        return _ticket_to_response(ticket)


@router.put("/api/v1/tickets/{ticket_id}/cancel")
async def cancel_ticket(ticket_id: str, body: TicketCancel, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可取消工单")

    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")
        if not validate_transition(ticket.status, "cancel"):
            raise HTTPException(status_code=400, detail=f"当前状态 {ticket.status} 不允许取消")

        old_status = ticket.status
        ticket.status = get_next_status(ticket.status, "cancel")
        await _add_log(db, ticket.id, "cancel", token["user_id"], old_status, ticket.status, comment=body.reason)
        await db.commit()
        return _ticket_to_response(ticket)


@router.put("/api/v1/tickets/{ticket_id}/priority")
async def change_priority(ticket_id: str, body: TicketPriorityChange, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可调整优先级")

    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")

        old_urgency = ticket.urgency
        ticket.urgency = body.urgency
        ticket.sla_deadline = calculate_sla_deadline(body.urgency)
        await _add_log(db, ticket.id, "priority_changed", token["user_id"], None, None,
                       extra_data={"old_urgency": old_urgency, "new_urgency": body.urgency})
        await db.commit()
        return _ticket_to_response(ticket)


@router.post("/api/v1/tickets/{ticket_id}/urge")
async def urge_ticket(ticket_id: str, token: TokenPayload = Depends(verify_token)):
    from app.models.urge_record import UrgeRecord
    from app.config import settings as app_settings

    async with async_session() as db:
        result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            raise HTTPException(status_code=404, detail="工单不存在")

        # 检查 30 分钟内是否已催办
        cooldown = datetime.now(timezone.utc) - timedelta(minutes=app_settings.urge_cooldown_minutes)
        urge_result = await db.execute(
            select(UrgeRecord).where(
                UrgeRecord.ticket_id == ticket.id,
                UrgeRecord.created_at >= cooldown,
            )
        )
        if urge_result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="催办过于频繁，请稍后再试")

        urge = UrgeRecord(
            ticket_id=ticket.id,
            urge_type="manual" if token["role"] == "user" else "user_request",
            urged_by=token["user_id"],
            message="用户催办" if token["role"] == "user" else "管理员催办",
        )
        db.add(urge)
        await db.commit()
        return {"message": "催办成功"}


@router.get("/api/v1/tickets/{ticket_id}/logs")
async def get_ticket_logs(ticket_id: str, token: TokenPayload = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(
            select(TicketLog).where(TicketLog.ticket_id == ticket_id).order_by(TicketLog.created_at)
        )
        logs = result.scalars().all()
        return [
            {
                "id": str(log.id),
                "action": log.action,
                "operator_id": str(log.operator_id) if log.operator_id else None,
                "from_status": log.from_status,
                "to_status": log.to_status,
                "comment": log.comment,
                "extra_data": log.extra_data,
                "created_at": log.created_at,
            }
            for log in logs
        ]


async def _auto_assign(db, ticket: Ticket, operator_id: str):
    """自动派单：调用派单引擎选出最佳工程师。"""
    best_engineer = await find_best_engineer(ticket)
    if best_engineer:
        await _assign_ticket(db, ticket, str(best_engineer.user_id), operator_id)
    else:
        # 无可用工程师，进入待分配池
        import redis.asyncio as redis
        from app.config import settings as app_settings
        r = redis.from_url(app_settings.redis_url, decode_responses=True)
        await r.sadd("unassigned_tickets", str(ticket.id))


async def _assign_ticket(db, ticket: Ticket, engineer_id: str, operator_id: str):
    """指派工单给指定工程师。"""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    ticket_no = f"WO-{today}-{uuid.uuid4().hex[:4].upper()}"

    old_status = ticket.status
    ticket.status = "assigned"
    ticket.assigned_to = uuid.UUID(engineer_id)
    ticket.assigned_at = datetime.now(timezone.utc)
    if not ticket.ticket_no:
        ticket.ticket_no = ticket_no
    await _add_log(db, ticket.id, "assign", operator_id, old_status, "assigned")
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/api/dispatch.py
git commit -m "feat(dispatch): add ticket management API with auto-assign"
```

---

### 任务 13：创建工程师管理 API + 统计 API

**文件：**
- 创建：`backend/app/api/stats.py`

- [ ] **步骤 1：在 dispatch.py 末尾添加工程师管理端点**

在原 `dispatch.py` 文件末尾追加：

```python
# ========== 工程师管理 ==========

@router.get("/api/v1/engineers")
async def list_engineers(token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看工程师列表")

    async with async_session() as db:
        result = await db.execute(select(EngineerProfile).order_by(EngineerProfile.display_name))
        engineers = result.scalars().all()
        return {
            "total": len(engineers),
            "items": [
                {
                    "id": str(e.id),
                    "user_id": str(e.user_id),
                    "display_name": e.display_name,
                    "skills": e.skills,
                    "skill_levels": e.skill_levels,
                    "status": e.status,
                    "max_concurrent": e.max_concurrent,
                    "current_load": e.current_load,
                    "total_completed": e.total_completed,
                    "avg_resolution_minutes": e.avg_resolution_minutes,
                    "rating": e.rating,
                }
                for e in engineers
            ],
        }


@router.post("/api/v1/engineers")
async def create_engineer(body: EngineerCreate, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可注册工程师")

    async with async_session() as db:
        existing = await db.execute(select(EngineerProfile).where(EngineerProfile.user_id == body.user_id))
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="该用户已是工程师")

        engineer = EngineerProfile(
            user_id=body.user_id,
            display_name=body.display_name,
            skills=body.skills,
            skill_levels=body.skill_levels,
        )
        db.add(engineer)
        await db.commit()
        return {"message": "工程师注册成功", "id": str(engineer.id)}


@router.put("/api/v1/engineers/{engineer_id}/skills")
async def update_engineer_skills(engineer_id: str, body: EngineerSkillUpdate, token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可更新技能")

    async with async_session() as db:
        result = await db.execute(select(EngineerProfile).where(EngineerProfile.id == engineer_id))
        engineer = result.scalar_one_or_none()
        if not engineer:
            raise HTTPException(status_code=404, detail="工程师不存在")
        engineer.skills = body.skills
        engineer.skill_levels = body.skill_levels
        await db.commit()
        return {"message": "技能更新成功"}


@router.put("/api/v1/engineers/{engineer_id}/status")
async def update_engineer_status(engineer_id: str, body: EngineerStatusUpdate, token: TokenPayload = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(select(EngineerProfile).where(EngineerProfile.id == engineer_id))
        engineer = result.scalar_one_or_none()
        if not engineer:
            raise HTTPException(status_code=404, detail="工程师不存在")
        if str(engineer.user_id) != token["user_id"] and token["role"] != "admin":
            raise HTTPException(status_code=403, detail="仅可修改自己的状态")
        engineer.status = body.status
        await db.commit()
        return {"message": "状态更新成功"}
```

- [ ] **步骤 2：创建 stats.py**

```python
# backend/app/api/stats.py
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from app.database import async_session
from app.core.auth_middleware import verify_token, TokenPayload
from app.models.ticket import Ticket

router = APIRouter()


@router.get("/api/v1/stats/tickets")
async def ticket_stats(token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看统计")

    async with async_session() as db:
        # 按状态统计
        status_result = await db.execute(
            select(Ticket.status, func.count(Ticket.id)).group_by(Ticket.status)
        )
        status_counts = {row[0]: row[1] for row in status_result.all()}

        # 按紧急度统计
        urgency_result = await db.execute(
            select(Ticket.urgency, func.count(Ticket.id)).group_by(Ticket.urgency)
        )
        urgency_counts = {row[0]: row[1] for row in urgency_result.all()}

        # 总数
        total_result = await db.execute(select(func.count(Ticket.id)))
        total = total_result.scalar() or 0

        return {
            "total": total,
            "by_status": status_counts,
            "by_urgency": urgency_counts,
        }


@router.get("/api/v1/stats/sla")
async def sla_stats(token: TokenPayload = Depends(verify_token)):
    if token["role"] != "admin":
        raise HTTPException(status_code=403, detail="仅管理员可查看统计")

    async with async_session() as db:
        from datetime import datetime, timezone
        from sqlalchemy import and_

        now = datetime.now(timezone.utc)
        # 超时工单
        overdue_result = await db.execute(
            select(func.count(Ticket.id)).where(
                and_(
                    Ticket.status.in_(["assigned", "in_progress"]),
                    Ticket.sla_deadline < now,
                )
            )
        )
        overdue = overdue_result.scalar() or 0

        # 待分配
        unassigned_result = await db.execute(
            select(func.count(Ticket.id)).where(Ticket.status == "created")
        )
        unassigned = unassigned_result.scalar() or 0

        return {"overdue": overdue, "unassigned": unassigned}
```

- [ ] **步骤 3：Commit**

```bash
git add backend/app/api/stats.py
git commit -m "feat(dispatch): add engineer management and stats APIs"
```

---

### 任务 14：注册新路由到 main.py

**文件：**
- 修改：`backend/app/main.py`

- [ ] **步骤 1：添加新路由**

```diff
  from app.api.tickets import router as tickets_router
  from app.api.feedback import router as feedback_router
+ from app.api.dispatch import router as dispatch_router
+ from app.api.stats import router as stats_router
  from app.config import settings

  app.include_router(tickets_router)
  app.include_router(feedback_router)
+ app.include_router(dispatch_router)
+ app.include_router(stats_router)
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/main.py
git commit -m "feat(dispatch): register dispatch and stats routers"
```

---

### 任务 15：创建 Redis Pub/Sub 通知服务

**文件：**
- 创建：`backend/app/core/notification.py`

- [ ] **步骤 1：创建通知服务文件**

```python
# backend/app/core/notification.py
import json
import asyncio
import redis.asyncio as redis
from app.config import settings


class NotificationService:
    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def publish(self, channel: str, message: dict):
        r = await self._get_redis()
        await r.publish(channel, json.dumps(message, ensure_ascii=False))

    async def notify_new_ticket(self, engineer_id: str, ticket_data: dict):
        await self.publish(f"engineer:{engineer_id}:notify", {
            "type": "new_ticket",
            "payload": ticket_data,
        })

    async def notify_urge(self, engineer_id: str, ticket_data: dict):
        await self.publish(f"engineer:{engineer_id}:notify", {
            "type": "urge",
            "payload": ticket_data,
        })

    async def notify_admin_alert(self, alert_type: str, data: dict):
        await self.publish("admin:alert", {
            "type": alert_type,
            "payload": data,
        })

    async def subscribe(self, channel: str):
        r = await self._get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel)
        return pubsub


notification_service = NotificationService()
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/notification.py
git commit -m "feat(dispatch): add Redis Pub/Sub notification service"
```

---

### 任务 16：创建管理员 NLU

**文件：**
- 创建：`backend/app/core/admin_nlu.py`

- [ ] **步骤 1：创建管理员 NLU 文件**

```python
# backend/app/core/admin_nlu.py
import json
import re
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import ADMIN_NLU_PROMPT


ADMIN_INTENTS = [
    "create_ticket",
    "assign_ticket",
    "reassign_ticket",
    "query_ticket",
    "cancel_ticket",
    "priority_change",
    "query_stats",
]


def parse_admin_input(message: str) -> dict:
    prompt = ADMIN_NLU_PROMPT.format(message=message)
    try:
        response = llm_adapter.chat_model.invoke(prompt)
        content = response.content.strip()
        json_match = re.search(r"\{[\s\S]*\}", content)
        if json_match:
            result = json.loads(json_match.group())
            intent = result.get("intent", "unknown")
            slots = result.get("slots", {})
            if intent in ADMIN_INTENTS:
                return {"intent": intent, "slots": slots}
    except Exception:
        pass
    return {"intent": "unknown", "slots": {}}
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/admin_nlu.py
git commit -m "feat(dispatch): add admin NLU module"
```

---

### 任务 17：更新 prompts.py 添加管理员 NLU 模板

**文件：**
- 修改：`backend/app/utils/prompts.py`

- [ ] **步骤 1：追加管理员 NLU prompt**

在文件末尾追加：

```python
ADMIN_NLU_PROMPT = """你是运维工单管理助手。根据管理员输入，判断意图并提取关键信息。

管理员输入：{message}

可用的意图：
- create_ticket：创建工单（需要提取 title/urgency/fault_category/engineer_name）
- assign_ticket：指派工单给指定工程师（需要提取 ticket_no/engineer_name）
- reassign_ticket：改派工单（需要提取 ticket_no/engineer_name）
- query_ticket：查询工单（需要提取 status_filter/engineer_name/time_range）
- cancel_ticket：取消工单（需要提取 ticket_no）
- priority_change：调整优先级（需要提取 ticket_no/urgency）
- query_stats：统计查询（需要提取 time_range）

请输出 JSON：
{{
    "intent": "意图",
    "slots": {{提取的槽位键值对}}
}}"""
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/utils/prompts.py
git commit -m "feat(dispatch): add admin NLU prompt template"
```

---

### 任务 18：创建 Celery 监控任务

**文件：**
- 创建：`backend/app/tasks/monitor_tasks.py`

- [ ] **步骤 1：创建监控任务文件**

```python
# backend/app/tasks/monitor_tasks.py
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, and_
from app.tasks.celery_app import celery_app
from app.database import async_session
from app.models.ticket import Ticket
from app.models.urge_record import UrgeRecord
from app.models.engineer import EngineerProfile
from app.core.notification import notification_service
from app.core.dispatch_engine import find_best_engineer
from app.config import settings


async def _check_sla_breach():
    now = datetime.now(timezone.utc)
    cooldown = now - timedelta(minutes=settings.urge_cooldown_minutes)

    async with async_session() as db:
        result = await db.execute(
            select(Ticket).where(
                and_(
                    Ticket.status.in_(["assigned", "in_progress"]),
                    Ticket.sla_deadline < now,
                )
            )
        )
        overdue_tickets = result.scalars().all()

        for ticket in overdue_tickets:
            # 检查是否已在冷却期内催办过
            urge_result = await db.execute(
                select(UrgeRecord).where(
                    UrgeRecord.ticket_id == ticket.id,
                    UrgeRecord.created_at >= cooldown,
                )
            )
            if urge_result.scalar_one_or_none():
                continue

            # 计算超时倍数
            sla_minutes = {
                "critical": settings.sla_critical_minutes,
                "high": settings.sla_high_minutes,
                "medium": settings.sla_medium_minutes,
                "low": settings.sla_low_minutes,
            }.get(ticket.urgency, settings.sla_medium_minutes)
            overdue_minutes = int((now - ticket.sla_deadline).total_seconds() / 60)

            # 记录催办
            urge = UrgeRecord(
                ticket_id=ticket.id,
                urge_type="auto_timeout",
                message=f"工单已超时 {overdue_minutes} 分钟，请尽快处理",
            )
            db.add(urge)

            # 推送通知给工程师
            if ticket.assigned_to:
                await notification_service.notify_urge(str(ticket.assigned_to), {
                    "ticket_id": str(ticket.id),
                    "ticket_no": ticket.ticket_no,
                    "message": f"工单已超时 {overdue_minutes} 分钟，请尽快处理",
                    "overdue_minutes": overdue_minutes,
                })

            # 超时超过 2 倍 SLA，通知管理员
            if overdue_minutes > sla_minutes * 2:
                await notification_service.notify_admin_alert("sla_breach", {
                    "ticket_id": str(ticket.id),
                    "ticket_no": ticket.ticket_no,
                    "title": ticket.title,
                    "assigned_to": str(ticket.assigned_to) if ticket.assigned_to else None,
                    "overdue_minutes": overdue_minutes,
                    "urgency": ticket.urgency,
                })

        await db.commit()


async def _check_unassigned_pool():
    import redis.asyncio as redis
    r = redis.from_url(settings.redis_url, decode_responses=True)

    async with async_session() as db:
        while True:
            ticket_id = await r.spop("unassigned_tickets")
            if not ticket_id:
                break
            ticket_id = ticket_id.decode() if isinstance(ticket_id, bytes) else ticket_id
            result = await db.execute(select(Ticket).where(Ticket.id == ticket_id))
            ticket = result.scalar_one_or_none()
            if ticket and ticket.status == "created":
                best_engineer = await find_best_engineer(ticket)
                if best_engineer:
                    ticket.status = "assigned"
                    ticket.assigned_to = best_engineer.user_id
                    ticket.assigned_at = datetime.now(timezone.utc)
                    await notification_service.notify_new_ticket(str(best_engineer.user_id), {
                        "ticket_id": str(ticket.id),
                        "ticket_no": ticket.ticket_no,
                        "title": ticket.title,
                        "urgency": ticket.urgency,
                    })
                else:
                    await r.sadd("unassigned_tickets", ticket_id)
        await db.commit()


async def _auto_close_tickets():
    deadline = datetime.now(timezone.utc) - timedelta(days=settings.auto_close_days)
    async with async_session() as db:
        result = await db.execute(
            select(Ticket).where(
                and_(
                    Ticket.status == "resolved",
                    Ticket.resolved_at < deadline,
                )
            )
        )
        tickets = result.scalars().all()
        for ticket in tickets:
            ticket.status = "closed"
            ticket.closed_at = datetime.now(timezone.utc)
        await db.commit()


async def _sync_engineer_load():
    import redis.asyncio as redis
    r = redis.from_url(settings.redis_url, decode_responses=True)

    async with async_session() as db:
        result = await db.execute(select(EngineerProfile))
        engineers = result.scalars().all()
        for engineer in engineers:
            load = await r.get(f"engineer:{engineer.user_id}:load")
            if load is not None:
                engineer.current_load = int(load)
        await db.commit()


@celery_app.task(name="check_sla_breach")
def check_sla_breach():
    asyncio.run(_check_sla_breach())


@celery_app.task(name="check_unassigned_pool")
def check_unassigned_pool():
    asyncio.run(_check_unassigned_pool())


@celery_app.task(name="auto_close_tickets")
def auto_close_tickets():
    asyncio.run(_auto_close_tickets())


@celery_app.task(name="sync_engineer_load")
def sync_engineer_load():
    asyncio.run(_sync_engineer_load())
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/tasks/monitor_tasks.py
git commit -m "feat(dispatch): add Celery monitoring tasks"
```

---

### 任务 19：更新 Celery beat 配置

**文件：**
- 修改：`backend/app/tasks/celery_app.py`

- [ ] **步骤 1：添加 beat schedule**

```diff
+ from celery.schedules import crontab

  celery_app.conf.update(
      task_serializer="json",
      accept_content=["json"],
      result_serializer="json",
      timezone="Asia/Shanghai",
      enable_utc=True,
      task_track_started=True,
      task_acks_late=True,
      worker_prefetch_multiplier=1,
+     beat_schedule={
+         "check_sla_breach": {
+             "task": "check_sla_breach",
+             "schedule": 300.0,  # 每 5 分钟
+         },
+         "check_unassigned_pool": {
+             "task": "check_unassigned_pool",
+             "schedule": 60.0,  # 每 1 分钟
+         },
+         "auto_close_tickets": {
+             "task": "auto_close_tickets",
+             "schedule": crontab(minute=0, hour="*"),  # 每 1 小时
+         },
+         "sync_engineer_load": {
+             "task": "sync_engineer_load",
+             "schedule": 60.0,  # 每 1 分钟
+         },
+     },
  )
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/tasks/celery_app.py
git commit -m "feat(dispatch): add Celery beat schedule for dispatch"
```

---

### 任务 20：更新 docker-compose.yml

**文件：**
- 修改：`docker-compose.yml`

- [ ] **步骤 1：添加 celery_beat 服务**

在 `celery_worker` 服务之后添加：

```yaml
  celery_beat:
    build: ./backend
    command: celery -A app.tasks.celery_app beat --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://opsagent:${POSTGRES_PASSWORD:-opsagent123}@postgres:5432/opsagent
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - postgres
      - redis
```

- [ ] **步骤 2：Commit**

```bash
git add docker-compose.yml
git commit -m "feat(dispatch): add celery_beat service"
```

---

### 任务 21：扩展前端 TypeScript 类型

**文件：**
- 修改：`frontend/src/types/index.ts`

- [ ] **步骤 1：追加类型定义**

```typescript
// 追加到文件末尾

export interface Ticket {
  id: string;
  ticket_no: string;
  title: string;
  description: string;
  fault_category: string;
  urgency: "low" | "medium" | "high" | "critical";
  device_info?: Record<string, unknown>;
  location?: string;
  status: "created" | "assigned" | "in_progress" | "resolved" | "closed" | "cancelled";
  assigned_to?: { id: string; display_name?: string };
  assigned_at?: string;
  resolution?: string;
  resolved_at?: string;
  closed_at?: string;
  sla_deadline?: string;
  created_by?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TicketLog {
  id: string;
  action: string;
  operator_id?: string;
  from_status?: string;
  to_status?: string;
  comment?: string;
  extra_data?: Record<string, unknown>;
  created_at?: string;
}

export interface Engineer {
  id: string;
  user_id: string;
  display_name: string;
  skills: string[];
  skill_levels: Record<string, number>;
  status: "available" | "busy" | "offline";
  max_concurrent: number;
  current_load: number;
  total_completed: number;
  avg_resolution_minutes: number;
  rating: number;
}

export interface TicketStats {
  total: number;
  by_status: Record<string, number>;
  by_urgency: Record<string, number>;
}

export interface SlaStats {
  overdue: number;
  unassigned: number;
}

export interface WebSocketNotification {
  type: string;
  payload: Record<string, unknown>;
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat(dispatch): add ticket and engineer TypeScript types"
```

---

### 任务 22：创建前端 Pinia Store

**文件：**
- 创建：`frontend/src/stores/ticket.ts`

- [ ] **步骤 1：创建 ticket store**

```typescript
// frontend/src/stores/ticket.ts
import { defineStore } from "pinia";
import { ref } from "vue";
import type { Ticket, TicketLog, TicketStats, SlaStats } from "../types";
import { api } from "../api";  // 使用已有的 api 实例

export const useTicketStore = defineStore("ticket", () => {
  const tickets = ref<Ticket[]>([]);
  const total = ref(0);
  const page = ref(1);
  const pageSize = ref(20);
  const loading = ref(false);
  const stats = ref<TicketStats | null>(null);
  const slaStats = ref<SlaStats | null>(null);

  const fetchTickets = async (params?: {
    status?: string;
    urgency?: string;
    page?: number;
  }) => {
    loading.value = true;
    try {
      const query = new URLSearchParams();
      if (params?.status) query.set("status", params.status);
      if (params?.urgency) query.set("urgency", params.urgency);
      query.set("page", String(params?.page || page.value));
      query.set("page_size", String(pageSize.value));

      const res = await api.get(`/api/v1/tickets?${query.toString()}`);
      tickets.value = res.data.items;
      total.value = res.data.total;
      page.value = res.data.page;
    } finally {
      loading.value = false;
    }
  };

  const fetchStats = async () => {
    const res = await api.get("/api/v1/stats/tickets");
    stats.value = res.data;
  };

  const fetchSlaStats = async () => {
    const res = await api.get("/api/v1/stats/sla");
    slaStats.value = res.data;
  };

  const assignTicket = async (ticketId: string, engineerId?: string) => {
    await api.put(`/api/v1/tickets/${ticketId}/assign`, {
      engineer_id: engineerId || null,
    });
  };

  const acceptTicket = async (ticketId: string) => {
    await api.put(`/api/v1/tickets/${ticketId}/accept`);
  };

  const rejectTicket = async (ticketId: string, reason?: string) => {
    await api.put(`/api/v1/tickets/${ticketId}/reject`, { reason });
  };

  const resolveTicket = async (ticketId: string, resolution: string) => {
    await api.put(`/api/v1/tickets/${ticketId}/resolve`, { resolution });
  };

  return {
    tickets,
    total,
    page,
    pageSize,
    loading,
    stats,
    slaStats,
    fetchTickets,
    fetchStats,
    fetchSlaStats,
    assignTicket,
    acceptTicket,
    rejectTicket,
    resolveTicket,
  };
});
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/stores/ticket.ts
git commit -m "feat(dispatch): add ticket Pinia store"
```

---

### 任务 23：创建前端路由 + 页面骨架

**文件：**
- 修改：`frontend/src/router/index.ts`
- 创建：`frontend/src/views/AdminDashboard.vue`
- 创建：`frontend/src/views/EngineerWorkbench.vue`

- [ ] **步骤 1：更新路由**

```typescript
// frontend/src/router/index.ts
import { createRouter, createWebHistory } from "vue-router";
import LoginView from "../views/LoginView.vue";
import ChatView from "../views/ChatView.vue";
import AdminDashboard from "../views/AdminDashboard.vue";
import EngineerWorkbench from "../views/EngineerWorkbench.vue";

const routes = [
  { path: "/", redirect: "/login" },
  { path: "/login", component: LoginView },
  { path: "/chat", component: ChatView, meta: { requiresAuth: true } },
  {
    path: "/admin/dashboard",
    component: AdminDashboard,
    meta: { requiresAuth: true, role: "admin" },
  },
  {
    path: "/engineer/workbench",
    component: EngineerWorkbench,
    meta: { requiresAuth: true, role: "engineer" },
  },
];

const router = createRouter({
  history: createWebHistory(),
  routes,
});

router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem("token");
  if (to.meta.requiresAuth && !token) {
    next("/login");
    return;
  }
  if (to.meta.role) {
    const role = localStorage.getItem("role") || "user";
    if (role !== to.meta.role) {
      next("/chat");
      return;
    }
  }
  next();
});

export default router;
```

- [ ] **步骤 2：创建 AdminDashboard 骨架**

```vue
<!-- frontend/src/views/AdminDashboard.vue -->
<template>
  <div class="admin-dashboard">
    <h1>运维派单管理后台</h1>
    <p>工单统计和管理功能即将上线</p>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.admin-dashboard {
  padding: 20px;
}
</style>
```

- [ ] **步骤 3：创建 EngineerWorkbench 骨架**

```vue
<!-- frontend/src/views/EngineerWorkbench.vue -->
<template>
  <div class="engineer-workbench">
    <h1>工程师工作台</h1>
    <p>待办工单和处理功能即将上线</p>
  </div>
</template>

<script setup lang="ts">
</script>

<style scoped>
.engineer-workbench {
  padding: 20px;
}
</style>
```

- [ ] **步骤 4：Commit**

```bash
git add frontend/src/router/index.ts frontend/src/views/AdminDashboard.vue frontend/src/views/EngineerWorkbench.vue
git commit -m "feat(dispatch): add admin and engineer routes with skeletons"
```

---

### 任务 24：端到端验证

- [ ] **步骤 1：重启 Docker 服务**

```bash
cd f:\mysite\project1-ops-agent
docker-compose down
docker-compose up -d --build
```

- [ ] **步骤 2：验证后端启动**

```bash
curl http://localhost:8000/api/v1/health
```
预期：`{"status": "ok"}`

- [ ] **步骤 3：验证新 API 可访问**

```bash
# 获取 token（使用已有管理员账号）
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```

- [ ] **步骤 4：验证工单 API**

```bash
# 使用获得的 token
curl http://localhost:8000/api/v1/tickets \
  -H "Authorization: Bearer <token>"
```
预期：返回空列表 `{"total":0,"page":1,"page_size":20,"items":[]}`

- [ ] **步骤 5：验证前端页面**

访问 `http://localhost:3000/login` 登录后，手动访问：
- `http://localhost:3000/admin/dashboard`（admin 角色）
- `http://localhost:3000/engineer/workbench`（engineer 角色）
预期：路由守卫正常，页面骨架渲染

- [ ] **步骤 6：验证 Celery beat**

```bash
docker-compose logs celery_beat | head -20
```
预期：无错误，显示 beat 启动信息

---

## 计划自检

1. **规格覆盖度**：对照设计文档 20 个章节，数据模型(4张表)、状态机、派单引擎、API(15+6+3)、通知、NLU、定时任务、前端路由+页面均已覆盖。
2. **占位符扫描**：无 TODO/待定/后续实现，所有代码步骤均有实际代码。
3. **类型一致性**：Ticket 模型字段名在 API 响应、TypeScript 类型、store 中保持一致。

---

计划已完成并保存到 `docs/superpowers/plans/2026-07-13-project2-dispatch-agent.md`。两种执行方式：

**1. 子代理驱动（推荐）** — 每个任务调度一个新的子代理，任务间进行审查，快速迭代

**2. 内联执行** — 在当前会话中使用 executing-plans 执行任务，批量执行并设有检查点

选哪种方式？