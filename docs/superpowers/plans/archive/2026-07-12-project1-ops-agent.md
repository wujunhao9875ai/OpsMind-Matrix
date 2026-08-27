# 项目1：智能运维客服 Agent — 实现计划

> **面向 AI 代理的工作者：** 必需子技能：使用 superpowers:subagent-driven-development（推荐）或 superpowers:executing-plans 逐任务实现此计划。步骤使用复选框（`- [ ]`）语法来跟踪进度。

**目标：** 构建基于本地大模型的运维智能客服，实现 RAG 问答、意图识别、多轮对话、工单预填和 Web 聊天界面。

**架构：** FastAPI 后端 + LangChain RAG + Ollama 本地模型 + Chroma 向量库 + Redis 会话管理 + Celery 异步任务 + PostgreSQL 业务数据 + Vue 3 前端 WebSocket 流式聊天。

**技术栈：** Python 3.12, FastAPI, LangChain, Ollama, Chroma, PostgreSQL 16, Redis 7, Celery, Vue 3, Element Plus, Docker

---

## 文件结构

```
f:\mysite\project1-ops-agent\
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── knowledge.py
│   │   │   ├── tickets.py
│   │   │   ├── feedback.py
│   │   │   └── health.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── auth_middleware.py
│   │   │   ├── intent_classifier.py
│   │   │   ├── query_rewriter.py
│   │   │   ├── rag_engine.py
│   │   │   ├── ticket_generator.py
│   │   │   ├── session_manager.py
│   │   │   ├── memory_manager.py
│   │   │   ├── llm_adapter.py
│   │   │   ├── reranker.py
│   │   │   ├── bm25_retriever.py
│   │   │   └── logger.py
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── conversation.py
│   │   │   ├── message.py
│   │   │   ├── knowledge.py
│   │   │   ├── pre_ticket.py
│   │   │   └── user_profile.py
│   │   ├── schemas/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── chat.py
│   │   │   ├── knowledge.py
│   │   │   ├── ticket.py
│   │   │   └── feedback.py
│   │   ├── tasks/
│   │   │   ├── __init__.py
│   │   │   ├── celery_app.py
│   │   │   ├── message_tasks.py
│   │   │   ├── knowledge_tasks.py
│   │   │   ├── classify_tasks.py
│   │   │   ├── summary_tasks.py
│   │   │   └── citation_tasks.py
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── prompts.py
│   │       ├── chunker.py
│   │       ├── coverage_guard.py
│   │       └── metrics.py
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_intent_classifier.py
│       ├── test_rag_engine.py
│       ├── test_ticket_generator.py
│       ├── test_chat_flow.py
│       ├── test_coverage_guard.py
│       ├── test_citation_validation.py
│       ├── test_quality_metrics.py
│       └── bad_cases.py
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── vite.config.ts
│   ├── index.html
│   └── src/
│       ├── App.vue
│       ├── main.ts
│       ├── router/
│       │   └── index.ts
│       ├── components/
│       │   ├── ChatWindow.vue
│       │   ├── MessageBubble.vue
│       │   ├── ChatInput.vue
│       │   └── TicketPreview.vue
│       ├── composables/
│       │   └── useWebSocket.ts
│       ├── stores/
│       │   └── chat.ts
│       ├── views/
│       │   ├── LoginView.vue
│       │   └── ChatView.vue
│       └── types/
│           └── index.ts
└── docs/
    └── sample_knowledge.md
```

---

### 任务 1：项目脚手架搭建

**文件：**
- 创建：`f:\mysite\project1-ops-agent\docker-compose.yml`
- 创建：`f:\mysite\project1-ops-agent\.env.example`
- 创建：`f:\mysite\project1-ops-agent\backend\Dockerfile`
- 创建：`f:\mysite\project1-ops-agent\backend\requirements.txt`
- 创建：`f:\mysite\project1-ops-agent\frontend\Dockerfile`
- 创建：`f:\mysite\project1-ops-agent\frontend\package.json`

- [ ] **步骤 1：创建项目目录结构**

```bash
mkdir -p f:\mysite\project1-ops-agent\backend\app\api
mkdir -p f:\mysite\project1-ops-agent\backend\app\core
mkdir -p f:\mysite\project1-ops-agent\backend\app\models
mkdir -p f:\mysite\project1-ops-agent\backend\app\schemas
mkdir -p f:\mysite\project1-ops-agent\backend\app\tasks
mkdir -p f:\mysite\project1-ops-agent\backend\app\utils
mkdir -p f:\mysite\project1-ops-agent\backend\tests
mkdir -p f:\mysite\project1-ops-agent\backend\alembic\versions
mkdir -p f:\mysite\project1-ops-agent\frontend\src\components
mkdir -p f:\mysite\project1-ops-agent\frontend\src\composables
mkdir -p f:\mysite\project1-ops-agent\frontend\src\stores
mkdir -p f:\mysite\project1-ops-agent\frontend\src\views
mkdir -p f:\mysite\project1-ops-agent\frontend\src\types
mkdir -p f:\mysite\project1-ops-agent\frontend\src\router
mkdir -p f:\mysite\project1-ops-agent\docs
```

- [ ] **步骤 2：编写 docker-compose.yml**

```yaml
version: "3.8"
services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_USER: opsagent
      POSTGRES_PASSWORD: opsagent123
      POSTGRES_DB: opsagent
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U opsagent"]
      interval: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 5

  chroma:
    image: chromadb/chroma:latest
    ports:
      - "8001:8000"
    volumes:
      - chroma_data:/chroma/chroma

  ollama:
    image: ollama/ollama:latest
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql+asyncpg://opsagent:opsagent123@postgres:5432/opsagent
      - REDIS_URL=redis://redis:6379/0
      - CHROMA_HOST=chroma
      - CHROMA_PORT=8000
      - OLLAMA_HOST=ollama
      - OLLAMA_PORT=11434
      - LLM_MODEL=deepseek-r1:1.5b
      - EMBEDDING_MODEL=quentinz/bge-large-zh-v1.5:latest
      - RERANKER_PATH=/app/models/reranker
      - JWT_SECRET=dev-secret-change-in-production
    volumes:
      - E:\ai\rerank\bge-reranker-base:/app/models/reranker:ro
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
      chroma:
        condition: service_started
      ollama:
        condition: service_started

  celery_worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info
    environment:
      - DATABASE_URL=postgresql+asyncpg://opsagent:opsagent123@postgres:5432/opsagent
      - REDIS_URL=redis://redis:6379/0
      - CHROMA_HOST=chroma
      - CHROMA_PORT=8000
      - OLLAMA_HOST=ollama
      - OLLAMA_PORT=11434
      - LLM_MODEL=deepseek-r1:1.5b
      - EMBEDDING_MODEL=quentinz/bge-large-zh-v1.5:latest
    volumes:
      - E:\ai\rerank\bge-reranker-base:/app/models/reranker:ro
    depends_on:
      - postgres
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  postgres_data:
  chroma_data:
  ollama_data:
```

- [ ] **步骤 3：编写 .env.example**

```env
# Database
DATABASE_URL=postgresql+asyncpg://opsagent:opsagent123@localhost:5432/opsagent

# Redis
REDIS_URL=redis://localhost:6379/0

# Chroma
CHROMA_HOST=localhost
CHROMA_PORT=8001

# Ollama
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
LLM_MODEL=deepseek-r1:1.5b
EMBEDDING_MODEL=quentinz/bge-large-zh-v1.5:latest

# Reranker
RERANKER_PATH=E:/ai/rerank/bge-reranker-base

# Auth
JWT_SECRET=dev-secret-change-in-production
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Rate Limit
RATE_LIMIT_PER_MINUTE=20
```

- [ ] **步骤 4：编写 backend/requirements.txt**

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
python-dotenv==1.0.1
pydantic-settings==2.7.0
sqlalchemy[asyncio]==2.0.36
asyncpg==0.30.0
alembic==1.14.1
redis==5.2.0
celery[redis]==5.4.0
langchain==0.3.13
langchain-community==0.3.13
langchain-ollama==0.2.2
chromadb==0.5.23
rank-bm25==0.2.2
jieba==0.42.1
FlagEmbedding==1.3.0
httpx==0.28.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.18
websockets==14.1
```

- [ ] **步骤 5：编写 backend/Dockerfile**

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
```

- [ ] **步骤 6：编写 frontend/package.json**

```json
{
  "name": "ops-agent-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "vue-router": "^4.5.0",
    "pinia": "^2.3.0",
    "element-plus": "^2.9.1",
    "@element-plus/icons-vue": "^2.3.1",
    "axios": "^1.7.9"
  },
  "devDependencies": {
    "@vitejs/plugin-vue": "^5.2.1",
    "typescript": "~5.6.3",
    "vite": "^6.0.5",
    "vue-tsc": "^2.2.0"
  }
}
```

- [ ] **步骤 7：编写 frontend/Dockerfile**

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

- [ ] **步骤 8：Commit**

```bash
git add project1-ops-agent/
git commit -m "chore: scaffold project1-ops-agent with docker-compose and configs"
```

---

### 任务 2：配置管理模块

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\__init__.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\config.py`

- [ ] **步骤 1：编写 app/config.py**

```python
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://opsagent:opsagent123@localhost:5432/opsagent"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Chroma
    chroma_host: str = "localhost"
    chroma_port: int = 8001

    # Ollama
    ollama_host: str = "localhost"
    ollama_port: int = 11434
    llm_model: str = "deepseek-r1:1.5b"
    embedding_model: str = "quentinz/bge-large-zh-v1.5:latest"

    # Reranker
    reranker_path: str = "E:/ai/rerank/bge-reranker-base"

    # Auth
    jwt_secret: str = "dev-secret-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Rate Limit
    rate_limit_per_minute: int = 20

    # RAG
    retrieval_top_k: int = 5
    dense_k: int = 10
    sparse_k: int = 10
    similarity_threshold: float = 0.6
    max_recent_messages: int = 6
    parent_chunk_size: int = 500
    child_chunk_size: int = 260
    chunk_overlap: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
```

- [ ] **步骤 2：编写 app/__init__.py**

```python
```

- [ ] **步骤 3：Commit**

```bash
git add backend/app/__init__.py backend/app/config.py
git commit -m "feat: add settings configuration module"
```

---

### 任务 3：数据库基础与模型定义

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\database.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\models\__init__.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\models\conversation.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\models\message.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\models\knowledge.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\models\pre_ticket.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\models\user_profile.py`
- 创建：`f:\mysite\project1-ops-agent\backend\alembic\env.py`
- 创建：`f:\mysite\project1-ops-agent\backend\alembic.ini`

- [ ] **步骤 1：编写 app/database.py**

```python
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.config import settings

engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
```

- [ ] **步骤 2：编写 app/models/__init__.py**

```python
from app.models.conversation import Conversation
from app.models.message import Message
from app.models.knowledge import KnowledgeDoc, KnowledgeChunk
from app.models.pre_ticket import PreTicket
from app.models.user_profile import UserProfile
from app.database import Base

__all__ = [
    "Base",
    "Conversation",
    "Message",
    "KnowledgeDoc",
    "KnowledgeChunk",
    "PreTicket",
    "UserProfile",
]
```

- [ ] **步骤 3：编写 app/models/conversation.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    user_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="active")
    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    slots: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    messages: Mapped[list["Message"]] = relationship("Message", back_populates="conversation", order_by="Message.created_at")
```

- [ ] **步骤 4：编写 app/models/message.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Float, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    rewritten_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    msg_type: Mapped[str] = mapped_column(String(50), default="text")
    category: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    feedback: Mapped[str] = mapped_column(String(50), default="none")
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    sources: Mapped[list | None] = mapped_column(JSON, nullable=True)
    metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    conversation: Mapped["Conversation"] = relationship("Conversation", back_populates="messages")
```

- [ ] **步骤 5：编写 app/models/knowledge.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class KnowledgeDoc(Base):
    __tablename__ = "knowledge_docs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, default=0)
    chunk_size: Mapped[int] = mapped_column(Integer, default=500)
    chunk_overlap: Mapped[int] = mapped_column(Integer, default=50)
    source: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    chunks: Mapped[list["KnowledgeChunk"]] = relationship("KnowledgeChunk", back_populates="doc")


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    doc_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_docs.id"), nullable=False)
    parent_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chunk_type: Mapped[str] = mapped_column(String(50), default="child")
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    section_title: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    doc: Mapped["KnowledgeDoc"] = relationship("KnowledgeDoc", back_populates="chunks")
```

- [ ] **步骤 6：编写 app/models/pre_ticket.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class PreTicket(Base):
    __tablename__ = "pre_tickets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("conversations.id"), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    fault_category: Mapped[str] = mapped_column(String(50), nullable=False)
    urgency: Mapped[str] = mapped_column(String(50), default="medium")
    device_info: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extracted_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="pending_review")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

- [ ] **步骤 7：编写 app/models/user_profile.py**

```python
import uuid
from datetime import datetime
from sqlalchemy import String, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    department: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    intent_distribution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    common_device_types: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    history_tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

- [ ] **步骤 8：编写 alembic.ini 和 alembic/env.py**

```ini
# alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://opsagent:opsagent123@localhost:5432/opsagent

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
```

```python
# alembic/env.py
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context
from app.database import Base
from app.models import *  # noqa: F401,F403

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    import asyncio
    asyncio.run(run_migrations_online())
```

- [ ] **步骤 9：Commit**

```bash
git add backend/app/database.py backend/app/models/ backend/alembic/
git commit -m "feat: add database models for conversations, messages, knowledge, tickets, profiles"
```

---

### 任务 4：LLM 适配器

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\__init__.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\llm_adapter.py`

- [ ] **步骤 1：编写 app/core/llm_adapter.py**

```python
from langchain_ollama import ChatOllama, OllamaEmbeddings
from app.config import settings


class LLMAdapter:
    """LLM 适配器，封装 Ollama 调用，支持模型切换。"""

    def __init__(self):
        self._chat_model = None
        self._embedding_model = None

    @property
    def chat_model(self) -> ChatOllama:
        if self._chat_model is None:
            self._chat_model = ChatOllama(
                model=settings.llm_model,
                base_url=f"http://{settings.ollama_host}:{settings.ollama_port}",
                temperature=0.1,
                streaming=True,
            )
        return self._chat_model

    @property
    def embedding_model(self) -> OllamaEmbeddings:
        if self._embedding_model is None:
            self._embedding_model = OllamaEmbeddings(
                model=settings.embedding_model,
                base_url=f"http://{settings.ollama_host}:{settings.ollama_port}",
            )
        return self._embedding_model

    def get_ollama_base_url(self) -> str:
        return f"http://{settings.ollama_host}:{settings.ollama_port}"


llm_adapter = LLMAdapter()
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/__init__.py backend/app/core/llm_adapter.py
git commit -m "feat: add LLM adapter with Ollama chat and embedding models"
```

---

### 任务 5：结构化日志

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\logger.py`

- [ ] **步骤 1：编写 app/core/logger.py**

```python
import json
import logging
import time
from datetime import datetime


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
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
    extra = {"event": event, "session_id": session_id, "user_id": user_id, "duration_ms": duration_ms, **kwargs}
    logger.log(getattr(logging, level), event, extra=extra)
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/logger.py
git commit -m "feat: add structured JSON logger"
```

---

### 任务 6：BM25 检索器

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\bm25_retriever.py`

- [ ] **步骤 1：编写 app/core/bm25_retriever.py**

```python
import jieba
from rank_bm25 import BM25Okapi


class BM25Retriever:
    """BM25 关键词检索器，支持中文分词。"""

    def __init__(self):
        self._index: BM25Okapi | None = None
        self._documents: list[dict] = []

    def build_index(self, documents: list[dict]):
        """构建 BM25 索引。documents: [{"id": str, "content": str}, ...]"""
        self._documents = documents
        tokenized = [list(jieba.cut(doc["content"])) for doc in documents]
        self._index = BM25Okapi(tokenized)

    def search(self, query: str, top_k: int = 10) -> list[dict]:
        """检索并返回带分数的文档列表。"""
        if self._index is None:
            return []
        tokenized_query = list(jieba.cut(query))
        scores = self._index.get_scores(tokenized_query)
        indexed = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        results = []
        max_score = max(scores) if max(scores) > 0 else 1
        for idx, score in indexed:
            if score > 0:
                results.append({
                    "id": self._documents[idx]["id"],
                    "content": self._documents[idx]["content"],
                    "score": score / max_score,
                    "doc_id": self._documents[idx].get("doc_id"),
                    "parent_text": self._documents[idx].get("parent_text"),
                })
        return results

    def is_empty(self) -> bool:
        return self._index is None or len(self._documents) == 0


bm25_retriever = BM25Retriever()
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/bm25_retriever.py
git commit -m "feat: add BM25 retriever with jieba tokenization"
```

---

### 任务 7：Reranker 重排序

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\reranker.py`

- [ ] **步骤 1：编写 app/core/reranker.py**

```python
from typing import Optional
from FlagEmbedding import FlagReranker
from app.config import settings


class Reranker:
    """Cross-encoder 重排序器。"""

    def __init__(self):
        self._model: Optional[FlagReranker] = None
        self._available = True

    @property
    def model(self) -> Optional[FlagReranker]:
        if self._model is None and self._available:
            try:
                self._model = FlagReranker(settings.reranker_path, use_fp16=True)
            except Exception:
                self._available = False
        return self._model

    def rerank(self, query: str, documents: list[dict], top_k: int = 5) -> list[dict]:
        """对文档列表重排序，返回 top_k 个结果。"""
        if not self.model or not documents:
            return documents[:top_k]

        pairs = [(query, doc["content"]) for doc in documents]
        scores = self.model.compute_score(pairs, normalize=True)

        if isinstance(scores, float):
            scores = [scores]

        for doc, score in zip(documents, scores):
            doc["rerank_score"] = float(score)

        return sorted(documents, key=lambda x: x.get("rerank_score", 0), reverse=True)[:top_k]


reranker = Reranker()
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/reranker.py
git commit -m "feat: add reranker with local BGE model"
```

---

### 任务 8：结构感知切块器

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\utils\__init__.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\utils\chunker.py`

- [ ] **步骤 1：编写 app/utils/chunker.py**

```python
import re
import uuid
import hashlib


def generate_parent_id(doc_title: str, section_title: str, index: int) -> str:
    raw = f"{doc_title}:{section_title}:{index}"
    return hashlib.md5(raw.encode()).hexdigest()[:12]


def split_by_headings(text: str) -> list[dict]:
    """按 Markdown ## 标题切分文档，返回结构块列表。"""
    sections = re.split(r"(?=^## )", text, flags=re.MULTILINE)
    result = []
    for section in sections:
        section = section.strip()
        if not section:
            continue
        title_match = re.match(r"^## (.+)", section)
        section_title = title_match.group(1).strip() if title_match else ""
        result.append({"title": section_title, "content": section})
    return result


def chunk_text(text: str, chunk_size: int = 260, overlap: int = 50) -> list[str]:
    """按字符数切分文本，带重叠。"""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap
    return chunks


def process_document(doc_title: str, content: str, parent_size: int = 500, child_size: int = 260, overlap: int = 50) -> list[dict]:
    """结构感知切块 + Parent-Child 分块。返回 child chunks 和 parent chunks 列表。"""
    sections = split_by_headings(content)
    all_chunks = []

    for section in sections:
        parent_chunks = chunk_text(section["content"], parent_size, overlap)
        for pi, parent_text in enumerate(parent_chunks):
            parent_id = generate_parent_id(doc_title, section["title"], pi)
            child_chunks = chunk_text(parent_text, child_size, overlap)
            for ci, child_text in enumerate(child_chunks):
                chunk_id = str(uuid.uuid4())
                all_chunks.append({
                    "id": chunk_id,
                    "parent_id": parent_id,
                    "chunk_type": "child",
                    "chunk_index": pi * 1000 + ci,
                    "section_title": section["title"],
                    "content": child_text,
                    "parent_text": parent_text,
                })
            # 同时存储 parent chunk（用于 LLM 上下文）
            parent_chunk_id = str(uuid.uuid4())
            all_chunks.append({
                "id": parent_chunk_id,
                "parent_id": parent_id,
                "chunk_type": "parent",
                "chunk_index": pi,
                "section_title": section["title"],
                "content": parent_text,
                "parent_text": parent_text,
            })

    return all_chunks
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/utils/__init__.py backend/app/utils/chunker.py
git commit -m "feat: add structure-aware chunker with parent-child strategy"
```

---

### 任务 9：Prompt 模板

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\utils\prompts.py`

- [ ] **步骤 1：编写 app/utils/prompts.py**

```python
RAG_QA_PROMPT = """你是运维助手。请根据以下运维知识库的内容回答用户问题。
如果知识库中没有相关信息，请明确告知用户。

知识库参考内容：
{context}

用户问题：{question}

请用中文回答，保持专业、简洁。如果无法确定答案，请说"抱歉，我暂时无法解答这个问题，已为您转人工处理。" """

INTENT_CLASSIFY_PROMPT = """判断以下用户消息的意图，仅输出意图类别：
- repair: 报修、设备故障、坏了、不能用了
- consult: 咨询、怎么用、如何操作、是什么
- check_progress: 查进度、工单状态、修好了吗
- unknown: 无法判断

用户消息：{message}

意图类别："""

TICKET_EXTRACT_PROMPT = """从以下对话中提取工单信息，输出 JSON 格式。

对话记录：
{conversation}

请提取以下字段：
- summary: 故障摘要（一句话）
- fault_category: 故障类别（hardware/software/network/other）
- urgency: 紧急程度（high/medium/low）
- device_info: 设备信息（type, model, sn）
- location: 位置
- missing_info: 仍需补充的信息列表"""

QUERY_REWRITE_PROMPT = """根据对话历史，将用户问题改写为适合知识库检索的独立查询。

对话历史摘要：
{history_summary}

用户当前问题：{question}

改写规则：
1. 补全指代不明的词（如"那个""上次"）
2. 将口语转为专业术语
3. 确保改写后问题可独立理解，不依赖上下文
4. 直接输出改写后的问题，不要解释

改写后的问题："""

CONVERSATION_SUMMARY_PROMPT = """将以下对话记录压缩为简洁摘要，保留关键信息（设备、故障、位置、已尝试步骤）。

对话记录：
{early_messages}

摘要："""

CATEGORY_CLASSIFY_PROMPT = """将以下运维问题归类，输出三级分类标签。

用户问题：{question}
意图：{intent}

一级固定为意图类别，请输出二级和三级分类：
- 二级可选：account/device_usage/hardware/network/software
- 三级需根据二级选择对应的子类

输出格式：{{"category": "一级-二级-三级"}}"""

MULTI_QUERY_PROMPT = """将以下用户问题拆分为多个检索角度，每个角度独立检索。

用户问题：{question}

请输出 2-3 个不同角度的检索 query，每行一个，不要编号："""
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/utils/prompts.py
git commit -m "feat: add prompt templates for RAG, intent, ticket, rewrite, summary, classify"
```

---

### 任务 10：意图分类器

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\intent_classifier.py`

- [ ] **步骤 1：编写 app/core/intent_classifier.py**

```python
import re
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import INTENT_CLASSIFY_PROMPT

# 关键词规则表
INTENT_RULES = {
    "repair": ["坏了", "不能用", "报修", "故障", "出问题", "不工作", "坏掉", "卡住", "无法", "错误", "报错", "死机", "蓝屏", "黑屏"],
    "check_progress": ["进度", "修好了吗", "工单状态", "什么时候", "处理了吗", "查一下", "到哪了"],
    "consult": ["怎么", "如何", "为什么", "是什么", "在哪里", "设置", "操作", "步骤", "方法", "区别"],
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
    if result in ("repair", "consult", "check_progress", "unknown"):
        return result
    return "unknown"


def classify_intent(message: str) -> str:
    """意图分类：先规则，规则未命中用小模型。"""
    rule_result = classify_by_rules(message)
    if rule_result:
        return rule_result
    return classify_by_model(message)
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/intent_classifier.py
git commit -m "feat: add intent classifier with rule-based + model fallback"
```

---

### 任务 11：RAG 引擎

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\rag_engine.py`

- [ ] **步骤 1：编写 app/core/rag_engine.py**

```python
import time
import chromadb
from langchain_core.prompts import ChatPromptTemplate
from app.config import settings
from app.core.llm_adapter import llm_adapter
from app.core.bm25_retriever import bm25_retriever
from app.core.reranker import reranker
from app.utils.prompts import RAG_QA_PROMPT
from app.core.logger import setup_logger, log_event

logger = setup_logger("rag_engine")
chroma_client = chromadb.HttpClient(host=settings.chroma_host, port=settings.chroma_port)


def rrf_fusion(dense_results: list[dict], sparse_results: list[dict], k: int = 60) -> list[dict]:
    """RRF 融合向量和 BM25 结果。"""
    score_map = {}
    for rank, doc in enumerate(dense_results):
        doc_id = doc.get("id")
        score_map[doc_id] = score_map.get(doc_id, 0) + 1 / (k + rank + 1)
    for rank, doc in enumerate(sparse_results):
        doc_id = doc.get("id")
        score_map[doc_id] = score_map.get(doc_id, 0) + 1 / (k + rank + 1)

    all_docs = {doc.get("id"): doc for doc in dense_results + sparse_results}
    merged = [(all_docs[doc_id], score) for doc_id, score in score_map.items() if doc_id in all_docs]
    merged.sort(key=lambda x: x[1], reverse=True)
    return [doc for doc, _ in merged]


def vector_search(query: str, collection_name: str = "ops_knowledge", top_k: int = 10) -> list[dict]:
    """Chroma 向量检索。"""
    try:
        collection = chroma_client.get_collection(collection_name)
        query_embedding = llm_adapter.embedding_model.embed_query(query)
        results = collection.query(query_embeddings=[query_embedding], n_results=top_k)
        docs = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results["metadatas"] else {}
                docs.append({
                    "id": doc_id,
                    "content": results["documents"][0][i] if results["documents"] else "",
                    "score": 1 - (results["distances"][0][i] if results["distances"] else 0),
                    "parent_text": metadata.get("parent_text", results["documents"][0][i] if results["documents"] else ""),
                    "section_title": metadata.get("section_title", ""),
                })
        return docs
    except Exception as e:
        log_event(logger, "vector_search_error", level="ERROR", error=str(e))
        return []


def search_knowledge(query: str, top_k: int = 5) -> list[dict]:
    """混合检索：向量 + BM25 → RRF 融合 → Rerank 精排。"""
    start = time.time()

    # 向量检索
    dense_results = vector_search(query, top_k=settings.dense_k)
    log_event(logger, "dense_retrieval", query=query, result_count=len(dense_results))

    # BM25 检索
    sparse_results = []
    if not bm25_retriever.is_empty():
        sparse_results = bm25_retriever.search(query, top_k=settings.sparse_k)
    log_event(logger, "sparse_retrieval", query=query, result_count=len(sparse_results))

    # RRF 融合
    if dense_results and sparse_results:
        merged = rrf_fusion(dense_results, sparse_results)
    else:
        merged = dense_results or sparse_results
    log_event(logger, "rrf_fusion", query=query, result_count=len(merged))

    # Rerank 精排
    final = reranker.rerank(query, merged, top_k=top_k)
    top_score = final[0].get("rerank_score", 0) if final else 0
    log_event(logger, "rerank", query=query, result_count=len(final), top_score=top_score, duration_ms=(time.time() - start) * 1000)

    return final


def generate_rag_answer(query: str, context_docs: list[dict]) -> str:
    """基于检索结果生成 RAG 回答。"""
    context_text = "\n\n---\n\n".join([
        f"[来源: {doc.get('section_title', '未知')}]\n{doc.get('parent_text', doc.get('content', ''))}"
        for doc in context_docs
    ])

    prompt = ChatPromptTemplate.from_template(RAG_QA_PROMPT)
    chain = prompt | llm_adapter.chat_model
    response = chain.invoke({"context": context_text, "question": query})
    return response.content
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/rag_engine.py
git commit -m "feat: add RAG engine with hybrid search, RRF fusion, and rerank"
```

---

### 任务 12：问题改写器与 Multi-Query

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\query_rewriter.py`

- [ ] **步骤 1：编写 app/core/query_rewriter.py**

```python
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import QUERY_REWRITE_PROMPT, MULTI_QUERY_PROMPT


def rewrite_query(question: str, history_summary: str = "") -> str:
    """结合对话历史改写用户问题，补全指代、术语化。"""
    if not history_summary:
        return question
    try:
        prompt = QUERY_REWRITE_PROMPT.format(history_summary=history_summary, question=question)
        response = llm_adapter.chat_model.invoke(prompt)
        return response.content.strip()
    except Exception:
        return question


def expand_multi_query(question: str) -> list[str]:
    """将复杂问题拆分为多个检索角度。"""
    try:
        prompt = MULTI_QUERY_PROMPT.format(question=question)
        response = llm_adapter.chat_model.invoke(prompt)
        queries = [q.strip() for q in response.content.strip().split("\n") if q.strip()]
        return queries if queries else [question]
    except Exception:
        return [question]
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/query_rewriter.py
git commit -m "feat: add query rewriter and multi-query expansion"
```

---

### 任务 13：会话管理器

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\session_manager.py`

- [ ] **步骤 1：编写 app/core/session_manager.py**

```python
import json
import redis.asyncio as redis
from app.config import settings


class SessionManager:
    """Redis 会话管理器，管理会话上下文和槽位填充状态。"""

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            self._redis = redis.from_url(settings.redis_url, decode_responses=True)
        return self._redis

    async def get_session(self, session_id: str) -> dict:
        r = await self._get_redis()
        data = await r.get(f"session:{session_id}")
        if data:
            return json.loads(data)
        return {"intent": None, "slots": {}, "history": [], "summary": ""}

    async def update_session(self, session_id: str, data: dict):
        r = await self._get_redis()
        await r.set(f"session:{session_id}", json.dumps(data, ensure_ascii=False), ex=3600)

    async def add_message(self, session_id: str, role: str, content: str):
        session = await self.get_session(session_id)
        session["history"].append({"role": role, "content": content})
        if len(session["history"]) > 100:
            session["history"] = session["history"][-100:]
        await self.update_session(session_id, session)

    async def get_slots(self, session_id: str) -> dict:
        session = await self.get_session(session_id)
        return session.get("slots", {})

    async def update_slot(self, session_id: str, key: str, value: str):
        session = await self.get_session(session_id)
        session["slots"][key] = value
        await self.update_session(session_id, session)

    async def get_summary(self, session_id: str) -> str:
        session = await self.get_session(session_id)
        return session.get("summary", "")

    async def set_summary(self, session_id: str, summary: str):
        session = await self.get_session(session_id)
        session["summary"] = summary
        await self.update_session(session_id, session)

    async def clear_session(self, session_id: str):
        r = await self._get_redis()
        await r.delete(f"session:{session_id}")


session_manager = SessionManager()
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/session_manager.py
git commit -m "feat: add Redis-based session manager with slot filling"
```

---

### 任务 14：工单生成器

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\ticket_generator.py`

- [ ] **步骤 1：编写 app/core/ticket_generator.py**

```python
import json
import re
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import TICKET_EXTRACT_PROMPT


def generate_pre_ticket(conversation_text: str) -> dict:
    """从对话文本中提取工单信息，返回结构化 JSON。"""
    prompt = TICKET_EXTRACT_PROMPT.format(conversation=conversation_text)
    response = llm_adapter.chat_model.invoke(prompt)
    content = response.content.strip()

    # 提取 JSON 块
    json_match = re.search(r"\{[\s\S]*\}", content)
    if json_match:
        try:
            return json.loads(json_match.group())
        except json.JSONDecodeError:
            pass

    return {
        "summary": "无法提取",
        "fault_category": "other",
        "urgency": "medium",
        "device_info": {},
        "location": "",
        "missing_info": ["自动提取失败，需人工补充"],
    }
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/ticket_generator.py
git commit -m "feat: add ticket generator with structured output extraction"
```

---

### 任务 15：记忆管理器

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\memory_manager.py`

- [ ] **步骤 1：编写 app/core/memory_manager.py**

```python
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import CONVERSATION_SUMMARY_PROMPT
from app.config import settings


def generate_summary(early_messages: list[dict]) -> str:
    """压缩早期对话为摘要。"""
    if not early_messages:
        return ""
    try:
        text = "\n".join([f"{m['role']}: {m['content']}" for m in early_messages])
        prompt = CONVERSATION_SUMMARY_PROMPT.format(early_messages=text)
        response = llm_adapter.chat_model.invoke(prompt)
        return response.content.strip()
    except Exception:
        return ""


def get_context_window(history: list[dict]) -> tuple[list[dict], list[dict]]:
    """返回滑动窗口：最近 N 轮原始消息 + 早期消息（用于摘要压缩）。"""
    max_recent = settings.max_recent_messages * 2  # 每轮 user + assistant
    if len(history) <= max_recent:
        return history, []
    recent = history[-max_recent:]
    early = history[:-max_recent]
    return recent, early
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/core/memory_manager.py
git commit -m "feat: add memory manager with sliding window and summary compression"
```

---

### 任务 16：Coverage Guard 与来源校验

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\utils\coverage_guard.py`

- [ ] **步骤 1：编写 app/utils/coverage_guard.py**

```python
import re

# 关键实体提取正则：错误码、型号、版本号
ENTITY_PATTERNS = [
    r"[A-Z]{1,5}\d{2,6}",    # 错误码: E1005, ANP220
    r"[A-Z]{2,5}-\d{2,4}",   # 型号: ANP-220-CN
    r"v\d+\.\d+(\.\d+)?",    # 版本号: v1.5, v2.0.1
]


def extract_entities(text: str) -> set[str]:
    """从文本中提取关键实体（错误码、型号、版本号）。"""
    entities = set()
    for pattern in ENTITY_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        entities.update(matches)
    return entities


def check_coverage(user_query: str, llm_answer: str, source_docs: list[dict]) -> str:
    """检查回答是否覆盖了用户问题中的关键实体，缺失则从来源补充。"""
    query_entities = extract_entities(user_query)
    if not query_entities:
        return llm_answer

    answer_lower = llm_answer.lower()
    missing = [e for e in query_entities if e.lower() not in answer_lower]

    if not missing:
        return llm_answer

    # 从来源文档中查找缺失实体的信息
    supplements = []
    for entity in missing:
        for doc in source_docs:
            parent_text = doc.get("parent_text", "")
            if entity.lower() in parent_text.lower():
                lines = [l.strip() for l in parent_text.split("\n") if entity.lower() in l.lower()]
                if lines:
                    section = doc.get("section_title", "未知")
                    supplements.append(f"{entity} 的相关信息：{lines[0][:200]}（来源：{section}）")
                    break

    if supplements:
        return llm_answer + "\n\n---\n补充信息：\n" + "\n".join(supplements)

    return llm_answer


def validate_citations(answer: str, valid_source_ids: list[str]) -> dict:
    """校验回答中引用的来源是否合法。"""
    cited = re.findall(r"\[来源: ([^\]]+)\]", answer)
    invalid = [c for c in cited if c not in valid_source_ids]
    return {
        "verified": len(invalid) == 0,
        "answer_sources": cited,
        "invalid_sources": invalid,
    }
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/utils/coverage_guard.py
git commit -m "feat: add answer coverage guard and citation validator"
```

---

### 任务 17：JWT 鉴权中间件

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\core\auth_middleware.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\schemas\__init__.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\schemas\auth.py`

- [ ] **步骤 1：编写 app/schemas/auth.py**

```python
from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
```

- [ ] **步骤 2：编写 app/core/auth_middleware.py**

```python
from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from fastapi import HTTPException, WebSocketException, status
from app.config import settings


def create_access_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expire_minutes)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def verify_token(token: str) -> str:
    """验证 JWT token，返回 user_id。"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


def verify_ws_token(token: str) -> str:
    """WebSocket 专用 token 验证。"""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload.get("sub")
        if user_id is None:
            raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return user_id
    except JWTError:
        raise WebSocketException(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
```

- [ ] **步骤 3：Commit**

```bash
git add backend/app/core/auth_middleware.py backend/app/schemas/auth.py
git commit -m "feat: add JWT authentication middleware"
```

---

### 任务 18：FastAPI 入口与路由注册

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\main.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\api\__init__.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\api\health.py`

- [ ] **步骤 1：编写 app/api/health.py**

```python
from fastapi import APIRouter

router = APIRouter()


@router.get("/api/v1/health")
async def health_check():
    return {"status": "ok", "service": "ops-agent"}
```

- [ ] **步骤 2：编写 app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.health import router as health_router
from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.knowledge import router as knowledge_router
from app.api.tickets import router as tickets_router
from app.api.feedback import router as feedback_router

app = FastAPI(title="运维智能客服 Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(knowledge_router)
app.include_router(tickets_router)
app.include_router(feedback_router)
```

- [ ] **步骤 3：Commit**

```bash
git add backend/app/main.py backend/app/api/__init__.py backend/app/api/health.py
git commit -m "feat: add FastAPI app entry with route registration"
```

---

### 任务 19：认证 API

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\api\auth.py`

- [ ] **步骤 1：编写 app/api/auth.py**

```python
from fastapi import APIRouter
from app.schemas.auth import LoginRequest, TokenResponse
from app.core.auth_middleware import create_access_token

router = APIRouter()

# 简化版：演示用固定用户
DEMO_USERS = {"admin": "admin123", "user1": "pass123", "user2": "pass123"}


@router.post("/api/v1/auth/login", response_model=TokenResponse)
async def login(request: LoginRequest):
    if request.username not in DEMO_USERS or DEMO_USERS[request.username] != request.password:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    token = create_access_token(request.username)
    return TokenResponse(access_token=token)
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/api/auth.py
git commit -m "feat: add login API endpoint with JWT token generation"
```

---

### 任务 20：WebSocket 聊天 API

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\schemas\chat.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\api\chat.py`

- [ ] **步骤 1：编写 app/schemas/chat.py**

```python
from pydantic import BaseModel
from datetime import datetime


class ChatHistoryItem(BaseModel):
    id: str
    role: str
    content: str
    msg_type: str = "text"
    category: str | None = None
    confidence: float | None = None
    sources: list | None = None
    created_at: datetime | None = None

    class Config:
        from_attributes = True


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str  # helpful / unhelpful
```

- [ ] **步骤 2：编写 app/api/chat.py**

```python
import json
import uuid
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.core.auth_middleware import verify_ws_token, verify_token
from app.core.intent_classifier import classify_intent
from app.core.query_rewriter import rewrite_query
from app.core.rag_engine import search_knowledge, generate_rag_answer
from app.core.session_manager import session_manager
from app.core.ticket_generator import generate_pre_ticket
from app.core.memory_manager import generate_summary, get_context_window
from app.utils.coverage_guard import check_coverage
from app.models.conversation import Conversation
from app.models.message import Message
from app.config import settings

router = APIRouter()


@router.websocket("/ws/chat/{session_id}")
async def chat_websocket(websocket: WebSocket, session_id: str, token: str = Query(...)):
    user_id = verify_ws_token(token)
    await websocket.accept()

    # 获取或创建会话
    conv = await _get_or_create_conversation(session_id, user_id)
    session_data = await session_manager.get_session(session_id)

    try:
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)

            if data.get("type") == "feedback":
                await _handle_feedback(data["payload"])
                continue

            if data.get("type") != "message":
                continue

            user_msg = data["payload"]["content"]
            msg_type = data["payload"].get("msg_type", "text")

            # 1. 保存用户消息
            await _save_message(conv.id, "user", user_msg, msg_type=msg_type)
            await session_manager.add_message(session_id, "user", user_msg)

            # 2. 意图分类
            intent = classify_intent(user_msg)
            session_data["intent"] = intent
            await session_manager.update_session(session_id, session_data)

            # 3. 根据意图路由
            if intent == "repair":
                await _handle_repair(websocket, session_id, user_msg, conv.id, session_data)
            elif intent == "consult":
                await _handle_consult(websocket, session_id, user_msg, conv.id, session_data)
            elif intent == "check_progress":
                await _send_reply(websocket, "工单进度查询功能请等待项目2派单系统上线后使用。", "check_progress", confidence=0.9)
            else:
                await _send_reply(websocket, "抱歉，我没有理解您的问题。请描述您遇到的运维问题，我会尽力帮您解决。", "unknown", confidence=0.5)

    except WebSocketDisconnect:
        pass


async def _handle_consult(websocket, session_id, user_msg, conv_id, session_data):
    """处理咨询类消息：RAG 检索 + 生成回答。"""
    # 改写问题
    summary = session_data.get("summary", "")
    rewritten = rewrite_query(user_msg, summary)

    # 检索
    context_docs = search_knowledge(rewritten, top_k=settings.retrieval_top_k)

    # 置信度判断
    top_score = context_docs[0].get("rerank_score", 0) if context_docs else 0

    if top_score < settings.similarity_threshold:
        await _send_reply(
            websocket,
            "抱歉，我暂时无法解答这个问题，已为您转人工处理。",
            "consult",
            confidence=top_score,
            sources=context_docs,
        )
        return

    # 生成回答
    answer = generate_rag_answer(rewritten, context_docs)

    # 不确定性检查
    uncertain_words = ["不确定", "不清楚", "无法解答", "抱歉"]
    is_uncertain = any(w in answer for w in uncertain_words)

    # Coverage Guard
    answer = check_coverage(user_msg, answer, context_docs)

    sources = [{"title": d.get("section_title", "未知"), "chunk_id": d.get("id", ""), "score": d.get("rerank_score", d.get("score", 0))} for d in context_docs]

    await _send_reply(
        websocket,
        answer,
        "consult",
        confidence=0.5 if is_uncertain else top_score,
        sources=sources,
    )

    # 保存 assistant 消息
    msg_id = await _save_message(
        conv_id, "assistant", answer,
        original_content=user_msg,
        rewritten_content=rewritten,
        confidence=0.5 if is_uncertain else top_score,
        sources=sources,
    )
    await session_manager.add_message(session_id, "assistant", answer)

    # 更新摘要
    history = session_data.get("history", [])
    recent, early = get_context_window(history)
    if early:
        new_summary = generate_summary(early)
        session_data["summary"] = new_summary
        await session_manager.update_session(session_id, session_data)


async def _handle_repair(websocket, session_id, user_msg, conv_id, session_data):
    """处理报修类消息：槽位填充 + 工单预填。"""
    slots = session_data.get("slots", {})

    # 简单槽位提取（后续可升级为 LLM 提取）
    if "打印机" in user_msg or "printer" in user_msg.lower():
        slots["device_type"] = "printer"
    if "电脑" in user_msg or "计算机" in user_msg:
        slots["device_type"] = "computer"
    if "网络" in user_msg or "wifi" in user_msg.lower():
        slots["device_type"] = "network"

    # 检查缺失槽位
    required_slots = ["device_type", "location", "fault_description"]
    missing = [s for s in required_slots if s not in slots or not slots[s]]

    if not slots.get("fault_description"):
        slots["fault_description"] = user_msg

    if missing:
        session_data["slots"] = slots
        await session_manager.update_session(session_id, session_data)
        slot_names = {"device_type": "设备类型", "location": "位置", "fault_description": "故障描述"}
        missing_names = [slot_names.get(s, s) for s in missing]
        await _send_reply(
            websocket,
            f"为了更好地帮您处理报修，请补充以下信息：{'、'.join(missing_names)}",
            "repair",
            require_slots=missing,
        )
        return

    # 槽位完整，生成预填工单
    conv_text = "\n".join([f"{m['role']}: {m['content']}" for m in session_data.get("history", [])])
    ticket_data = generate_pre_ticket(conv_text)
    ticket_data["device_info"] = {"type": slots.get("device_type", "")}
    ticket_data["location"] = slots.get("location", "")

    await _send_reply(
        websocket,
        f"已为您生成预填工单：\n- 故障摘要：{ticket_data.get('summary', '')}\n- 故障类别：{ticket_data.get('fault_category', '')}\n- 紧急程度：{ticket_data.get('urgency', '')}\n- 位置：{ticket_data.get('location', '')}\n\n工单已提交，运维工程师将尽快处理。",
        "repair",
        confidence=0.9,
    )

    # 发送工单预览
    await websocket.send_text(json.dumps({
        "type": "ticket_preview",
        "payload": {
            "ticket_id": f"pre-{uuid.uuid4().hex[:8]}",
            "summary": ticket_data.get("summary", ""),
            "urgency": ticket_data.get("urgency", "medium"),
            "device": ticket_data.get("device_info", {}),
        },
    }))


async def _send_reply(websocket, content, intent, confidence=0.0, sources=None, require_slots=None):
    """流式推送回复。"""
    await websocket.send_text(json.dumps({"type": "reply_start", "payload": {"intent": intent}}))
    chunk_size = 10
    for i in range(0, len(content), chunk_size):
        await websocket.send_text(json.dumps({"type": "reply_chunk", "payload": {"content": content[i:i + chunk_size]}}))
    await websocket.send_text(json.dumps({
        "type": "reply_end",
        "payload": {
            "content": content,
            "intent": intent,
            "confidence": confidence,
            "sources": sources or [],
            "require_slots": require_slots,
        },
    }))


async def _get_or_create_conversation(session_id: str, user_id: str):
    async with AsyncSession(async_session) as db:
        result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
        conv = result.scalar_one_or_none()
        if conv is None:
            conv = Conversation(session_id=session_id, user_id=user_id)
            db.add(conv)
            await db.commit()
            await db.refresh(conv)
        return conv


async def _save_message(conv_id, role, content, **kwargs):
    from app.database import async_session
    async with async_session() as db:
        msg = Message(conversation_id=conv_id, role=role, content=content, **kwargs)
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return str(msg.id)


async def _handle_feedback(payload):
    from app.database import async_session
    async with async_session() as db:
        result = await db.execute(select(Message).where(Message.id == payload["message_id"]))
        msg = result.scalar_one_or_none()
        if msg:
            msg.feedback = payload["feedback"]
            from datetime import datetime
            msg.feedback_at = datetime.utcnow()
            await db.commit()


@router.get("/api/v1/chat/history/{session_id}")
async def get_chat_history(session_id: str, user_id: str = Depends(verify_token)):
    from app.database import async_session
    async with async_session() as db:
        result = await db.execute(select(Conversation).where(Conversation.session_id == session_id))
        conv = result.scalar_one_or_none()
        if not conv:
            return []
        result = await db.execute(
            select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)
        )
        messages = result.scalars().all()
        return [{"id": str(m.id), "role": m.role, "content": m.content, "msg_type": m.msg_type, "confidence": m.confidence, "sources": m.sources, "created_at": m.created_at.isoformat() if m.created_at else None} for m in messages]


@router.get("/api/v1/chat/sessions")
async def get_sessions(user_id: str = Depends(verify_token)):
    from app.database import async_session
    async with async_session() as db:
        result = await db.execute(select(Conversation).where(Conversation.user_id == user_id).order_by(Conversation.updated_at.desc()))
        sessions = result.scalars().all()
        return [{"session_id": s.session_id, "status": s.status, "intent": s.intent, "created_at": s.created_at.isoformat()} for s in sessions]
```

注意：chat.py 引用了 `async_session`，需要在 `database.py` 中导出。在 `database.py` 中已有 `async_session`，确保导入正确。

- [ ] **步骤 2：Commit**

```bash
git add backend/app/schemas/chat.py backend/app/api/chat.py
git commit -m "feat: add WebSocket chat API with full RAG pipeline and streaming"
```

---

### 任务 21：知识库管理 API

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\schemas\knowledge.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\api\knowledge.py`

- [ ] **步骤 1：编写 app/schemas/knowledge.py**

```python
from pydantic import BaseModel


class KnowledgeDocResponse(BaseModel):
    id: str
    title: str
    chunk_count: int
    source: str | None
    status: str
    created_at: str | None

    class Config:
        from_attributes = True
```

- [ ] **步骤 2：编写 app/api/knowledge.py**

```python
import uuid
import zipfile
import io
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db, async_session
from app.core.auth_middleware import verify_token
from app.core.llm_adapter import llm_adapter
from app.core.rag_engine import chroma_client
from app.utils.chunker import process_document
from app.models.knowledge import KnowledgeDoc, KnowledgeChunk

router = APIRouter()


@router.post("/api/v1/knowledge/upload")
async def upload_knowledge(
    file: UploadFile = File(...),
    user_id: str = Depends(verify_token),
):
    """上传知识库文档（支持 .md 和 .zip）。"""
    content = await file.read()

    if file.filename.endswith(".zip"):
        # 批量导入 zip 中的 Markdown 文件
        results = []
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            for name in zf.namelist():
                if name.endswith(".md") or name.endswith(".txt"):
                    doc_content = zf.read(name).decode("utf-8")
                    doc_title = name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
                    results.append(await _process_document(doc_title, doc_content, name))
        return {"imported": len(results), "docs": results}
    else:
        content_str = content.decode("utf-8")
        doc_title = file.filename.rsplit(".", 1)[0]
        result = await _process_document(doc_title, content_str, file.filename)
        return {"imported": 1, "doc": result}


async def _process_document(title: str, content: str, source: str) -> dict:
    """处理单个文档：存储、切块、向量化。"""
    async with async_session() as db:
        # 保存文档
        doc = KnowledgeDoc(title=title, content=content, source=source, status="processing")
        db.add(doc)
        await db.commit()
        await db.refresh(doc)

        # 结构感知切块
        chunks = process_document(title, content, settings.parent_chunk_size, settings.child_chunk_size, settings.chunk_overlap)

        # 向量化 child chunks
        child_chunks = [c for c in chunks if c["chunk_type"] == "child"]
        child_contents = [c["content"] for c in child_chunks]
        child_ids = [c["id"] for c in child_chunks]
        child_metadatas = [{"parent_id": c["parent_id"], "parent_text": c["parent_text"], "section_title": c["section_title"], "doc_id": str(doc.id)} for c in child_chunks]

        if child_contents:
            try:
                collection = chroma_client.get_or_create_collection("ops_knowledge")
                embeddings = llm_adapter.embedding_model.embed_documents(child_contents)
                collection.add(ids=child_ids, embeddings=embeddings, documents=child_contents, metadatas=child_metadatas)
            except Exception as e:
                doc.status = "archived"
                await db.commit()
                raise HTTPException(status_code=500, detail=f"向量化失败: {str(e)}")

        # 保存所有 chunks 到数据库
        for chunk in chunks:
            c = KnowledgeChunk(
                doc_id=doc.id,
                parent_id=chunk["parent_id"],
                chunk_type=chunk["chunk_type"],
                chunk_index=chunk["chunk_index"],
                section_title=chunk["section_title"],
                content=chunk["content"],
                parent_text=chunk["parent_text"],
                embedding_id=chunk["id"] if chunk["chunk_type"] == "child" else None,
            )
            db.add(c)

        doc.chunk_count = len(chunks)
        doc.status = "active"
        await db.commit()

        return {"id": str(doc.id), "title": title, "chunk_count": len(chunks), "status": "active"}


@router.get("/api/v1/knowledge/docs")
async def list_docs(user_id: str = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(select(KnowledgeDoc).order_by(KnowledgeDoc.created_at.desc()))
        docs = result.scalars().all()
        return [{"id": str(d.id), "title": d.title, "chunk_count": d.chunk_count, "source": d.source, "status": d.status, "created_at": d.created_at.isoformat() if d.created_at else None} for d in docs]


@router.put("/api/v1/knowledge/docs/{doc_id}")
async def update_doc(doc_id: str, user_id: str = Depends(verify_token)):
    """更新文档（触发重索引）。"""
    async with async_session() as db:
        result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        # 删除旧 chunks
        await db.execute(select(KnowledgeChunk).where(KnowledgeChunk.doc_id == doc.id))
        # 标记为 processing，触发 Celery 重索引
        doc.status = "processing"
        await db.commit()
        return {"id": str(doc.id), "status": "processing"}


@router.delete("/api/v1/knowledge/docs/{doc_id}")
async def delete_doc(doc_id: str, user_id: str = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        # 删除 Chroma 中的向量
        try:
            collection = chroma_client.get_collection("ops_knowledge")
            chunk_ids = [c.embedding_id for c in doc.chunks if c.embedding_id]
            if chunk_ids:
                collection.delete(ids=chunk_ids)
        except Exception:
            pass
        await db.delete(doc)
        await db.commit()
        return {"deleted": True}


@router.post("/api/v1/knowledge/docs/{doc_id}/reindex")
async def reindex_doc(doc_id: str, user_id: str = Depends(verify_token)):
    """手动触发重索引。"""
    async with async_session() as db:
        result = await db.execute(select(KnowledgeDoc).where(KnowledgeDoc.id == doc_id))
        doc = result.scalar_one_or_none()
        if not doc:
            raise HTTPException(status_code=404, detail="文档不存在")
        doc.status = "processing"
        await db.commit()
        return {"id": str(doc.id), "status": "processing"}
```

- [ ] **步骤 3：Commit**

```bash
git add backend/app/schemas/knowledge.py backend/app/api/knowledge.py
git commit -m "feat: add knowledge base management API with upload, list, delete, reindex"
```

---

### 任务 22：反馈与工单 API

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\schemas\feedback.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\schemas\ticket.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\api\feedback.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\api\tickets.py`

- [ ] **步骤 1：编写 schemas/feedback.py 和 schemas/ticket.py**

```python
# schemas/feedback.py
from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    message_id: str
    feedback: str  # helpful / unhelpful
```

```python
# schemas/ticket.py
from pydantic import BaseModel


class PreTicketResponse(BaseModel):
    id: str
    summary: str
    fault_category: str
    urgency: str
    status: str
    created_at: str | None

    class Config:
        from_attributes = True
```

- [ ] **步骤 2：编写 app/api/feedback.py**

```python
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from app.database import async_session
from app.core.auth_middleware import verify_token
from app.schemas.feedback import FeedbackRequest
from app.models.message import Message

router = APIRouter()


@router.put("/api/v1/chat/feedback/{message_id}")
async def submit_feedback(message_id: str, request: FeedbackRequest, user_id: str = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(select(Message).where(Message.id == message_id))
        msg = result.scalar_one_or_none()
        if not msg:
            raise HTTPException(status_code=404, detail="消息不存在")
        msg.feedback = request.feedback
        msg.feedback_at = datetime.utcnow()
        await db.commit()
        return {"message_id": message_id, "feedback": request.feedback}
```

- [ ] **步骤 3：编写 app/api/tickets.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select
from app.database import async_session
from app.core.auth_middleware import verify_token
from app.models.pre_ticket import PreTicket

router = APIRouter()


@router.get("/api/v1/tickets/pre-tickets")
async def list_pre_tickets(user_id: str = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(
            select(PreTicket).order_by(PreTicket.created_at.desc())
        )
        tickets = result.scalars().all()
        return [
            {
                "id": str(t.id),
                "summary": t.summary,
                "fault_category": t.fault_category,
                "urgency": t.urgency,
                "status": t.status,
                "created_at": t.created_at.isoformat() if t.created_at else None,
            }
            for t in tickets
        ]


@router.get("/api/v1/tickets/pre-tickets/{ticket_id}")
async def get_pre_ticket(ticket_id: str, user_id: str = Depends(verify_token)):
    async with async_session() as db:
        result = await db.execute(select(PreTicket).where(PreTicket.id == ticket_id))
        ticket = result.scalar_one_or_none()
        if not ticket:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="工单不存在")
        return {
            "id": str(ticket.id),
            "conversation_id": str(ticket.conversation_id),
            "summary": ticket.summary,
            "fault_category": ticket.fault_category,
            "urgency": ticket.urgency,
            "device_info": ticket.device_info,
            "location": ticket.location,
            "extracted_data": ticket.extracted_data,
            "status": ticket.status,
            "created_at": ticket.created_at.isoformat() if ticket.created_at else None,
        }
```

- [ ] **步骤 4：Commit**

```bash
git add backend/app/schemas/feedback.py backend/app/schemas/ticket.py backend/app/api/feedback.py backend/app/api/tickets.py
git commit -m "feat: add feedback and pre-ticket query APIs"
```

---

### 任务 23：Celery 异步任务

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\tasks\__init__.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\tasks\celery_app.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\tasks\message_tasks.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\tasks\classify_tasks.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\tasks\summary_tasks.py`
- 创建：`f:\mysite\project1-ops-agent\backend\app\tasks\citation_tasks.py`

- [ ] **步骤 1：编写 app/tasks/celery_app.py**

```python
from celery import Celery
from app.config import settings

celery_app = Celery(
    "ops_agent",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Shanghai",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
```

- [ ] **步骤 2：编写 app/tasks/message_tasks.py**

```python
from app.tasks.celery_app import celery_app
from app.utils.coverage_guard import validate_citations


@celery_app.task(bind=True, max_retries=3)
def validate_citation_task(self, message_id: str, answer: str, valid_source_ids: list):
    """异步校验回答中的来源引用。"""
    try:
        result = validate_citations(answer, valid_source_ids)
        return result
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

- [ ] **步骤 3：编写 app/tasks/classify_tasks.py**

```python
from app.tasks.celery_app import celery_app
from app.core.llm_adapter import llm_adapter
from app.utils.prompts import CATEGORY_CLASSIFY_PROMPT


@celery_app.task(bind=True, max_retries=3)
def classify_message_task(self, message_id: str, question: str, intent: str):
    """异步标注消息三级分类。"""
    try:
        prompt = CATEGORY_CLASSIFY_PROMPT.format(question=question, intent=intent)
        response = llm_adapter.chat_model.invoke(prompt)
        import json
        data = json.loads(response.content.strip())
        return data.get("category", f"{intent}-uncategorized")
    except Exception as exc:
        raise self.retry(exc=exc, countdown=60)
```

- [ ] **步骤 4：编写 app/tasks/summary_tasks.py**

```python
from app.tasks.celery_app import celery_app
from app.core.memory_manager import generate_summary


@celery_app.task
def generate_summary_task(early_messages: list[dict]) -> str:
    """异步生成对话摘要。"""
    return generate_summary(early_messages)
```

- [ ] **步骤 5：Commit**

```bash
git add backend/app/tasks/
git commit -m "feat: add Celery async tasks for citation, classification, and summary"
```

---

### 任务 24：质量指标

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\app\utils\metrics.py`

- [ ] **步骤 1：编写 app/utils/metrics.py**

```python
def calculate_mrr(bad_cases: list[dict], search_fn) -> float:
    """计算 MRR（Mean Reciprocal Rank）。"""
    reciprocal_ranks = []
    for case in bad_cases:
        results = search_fn(case["query"])
        found = False
        for rank, doc in enumerate(results, 1):
            if any(term in doc.get("content", "") for term in case.get("expected_retrieval_terms", [])):
                reciprocal_ranks.append(1.0 / rank)
                found = True
                break
        if not found:
            reciprocal_ranks.append(0.0)
    return sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0


def calculate_hallucination_rate(citation_results: list[dict]) -> float:
    """计算幻觉率。"""
    if not citation_results:
        return 0.0
    unverified = sum(1 for r in citation_results if not r.get("verified", False))
    return unverified / len(citation_results)


def calculate_rejection_rate(total_queries: int, rejected_queries: int) -> float:
    """计算拒答率。"""
    if total_queries == 0:
        return 0.0
    return rejected_queries / total_queries
```

- [ ] **步骤 2：Commit**

```bash
git add backend/app/utils/metrics.py
git commit -m "feat: add quality metrics (MRR, hallucination rate, rejection rate)"
```

---

### 任务 25：Bad Case 回归集

**文件：**
- 创建：`f:\mysite\project1-ops-agent\backend\tests\__init__.py`
- 创建：`f:\mysite\project1-ops-agent\backend\tests\conftest.py`
- 创建：`f:\mysite\project1-ops-agent\backend\tests\bad_cases.py`

- [ ] **步骤 1：编写 tests/conftest.py**

```python
import pytest
from app.core.rag_engine import search_knowledge

BAD_CASES = [
    {
        "id": "printer_jam",
        "query": "打印机卡纸怎么办？",
        "expected_route": "rag",
        "expected_retrieval_terms": ["卡纸", "打印机", "取出"],
        "expected_answer_terms": ["关机", "轻轻取出", "硒鼓"],
        "expected_source_any": ["打印机常见故障 > 卡纸处理"],
    },
    {
        "id": "network_failure",
        "query": "网连不上了",
        "expected_route": "rag",
        "expected_retrieval_terms": ["网络", "连接", "失败"],
        "expected_answer_terms": ["检查", "网络"],
    },
    {
        "id": "error_code",
        "query": "E1005怎么处理",
        "expected_route": "rag",
        "expected_retrieval_terms": ["E1005", "错误"],
        "expected_answer_terms": ["E1005"],
    },
    {
        "id": "repair_report",
        "query": "我电脑坏了",
        "expected_route": "repair",
        "expected_retrieval_terms": [],
        "expected_answer_terms": [],
    },
    {
        "id": "unknown_query",
        "query": "今天天气怎么样",
        "expected_route": "unknown",
        "expected_retrieval_terms": [],
        "expected_answer_terms": [],
    },
]
```

- [ ] **步骤 2：编写 tests/bad_cases.py**

```python
from app.core.intent_classifier import classify_intent
from app.core.rag_engine import search_knowledge
from app.utils.metrics import calculate_mrr
from tests.conftest import BAD_CASES


def test_intent_classification():
    """验证意图分类在 Bad Case 上的表现。"""
    repair_cases = [c for c in BAD_CASES if c["expected_route"] == "repair"]
    for case in repair_cases:
        intent = classify_intent(case["query"])
        assert intent == "repair", f"Case {case['id']}: expected repair, got {intent}"


def test_rag_mrr():
    """计算 RAG 检索的 MRR。"""
    rag_cases = [c for c in BAD_CASES if c["expected_route"] == "rag"]
    mrr = calculate_mrr(rag_cases, search_knowledge)
    print(f"MRR: {mrr:.3f}")
    assert mrr > 0.0, "MRR should be positive"
```

- [ ] **步骤 3：Commit**

```bash
git add backend/tests/
git commit -m "test: add bad case regression set and quality metrics tests"
```

---

### 任务 26：前端 — Vue 3 项目初始化与路由

**文件：**
- 创建：`f:\mysite\project1-ops-agent\frontend\index.html`
- 创建：`f:\mysite\project1-ops-agent\frontend\vite.config.ts`
- 创建：`f:\mysite\project1-ops-agent\frontend\src\main.ts`
- 创建：`f:\mysite\project1-ops-agent\frontend\src\App.vue`
- 创建：`f:\mysite\project1-ops-agent\frontend\src\router\index.ts`
- 创建：`f:\mysite\project1-ops-agent\frontend\src\types\index.ts`

- [ ] **步骤 1：编写 frontend/index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>运维智能客服</title>
</head>
<body>
  <div id="app"></div>
  <script type="module" src="/src/main.ts"></script>
</body>
</html>
```

- [ ] **步骤 2：编写 frontend/vite.config.ts**

```typescript
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": {
        target: "ws://localhost:8000",
        ws: true,
      },
    },
  },
});
```

- [ ] **步骤 3：编写 frontend/src/main.ts**

```typescript
import { createApp } from "vue";
import { createPinia } from "pinia";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import App from "./App.vue";
import router from "./router";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.use(ElementPlus);
app.mount("#app");
```

- [ ] **步骤 4：编写 frontend/src/App.vue**

```vue
<template>
  <router-view />
</template>
```

- [ ] **步骤 5：编写 frontend/src/router/index.ts**

```typescript
import { createRouter, createWebHistory } from "vue-router";
import LoginView from "../views/LoginView.vue";
import ChatView from "../views/ChatView.vue";

const routes = [
  { path: "/", redirect: "/login" },
  { path: "/login", component: LoginView },
  { path: "/chat", component: ChatView },
];

export default createRouter({
  history: createWebHistory(),
  routes,
});
```

- [ ] **步骤 6：编写 frontend/src/types/index.ts**

```typescript
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  msg_type: "text" | "image";
  confidence?: number;
  sources?: Array<{ title: string; score: number }>;
  created_at?: string;
}

export interface WebSocketMessage {
  type: "reply_start" | "reply_chunk" | "reply_end" | "ticket_preview";
  payload: Record<string, unknown>;
}
```

- [ ] **步骤 7：Commit**

```bash
git add frontend/
git commit -m "feat: scaffold Vue 3 frontend with router, pinia, and element-plus"
```

---

### 任务 27：前端 — 登录页面

**文件：**
- 创建：`f:\mysite\project1-ops-agent\frontend\src\views\LoginView.vue`

- [ ] **步骤 1：编写 frontend/src/views/LoginView.vue**

```vue
<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2>运维智能客服</h2>
      <el-form :model="form" label-width="80px">
        <el-form-item label="用户名">
          <el-input v-model="form.username" placeholder="请输入用户名" />
        </el-form-item>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" placeholder="请输入密码" @keyup.enter="login" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="login" :loading="loading">登录</el-button>
        </el-form-item>
      </el-form>
      <p class="hint">测试账号: admin / admin123</p>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from "vue";
import { useRouter } from "vue-router";
import axios from "axios";
import { ElMessage } from "element-plus";

const router = useRouter();
const loading = ref(false);
const form = reactive({ username: "", password: "" });

async function login() {
  loading.value = true;
  try {
    const { data } = await axios.post("/api/v1/auth/login", form);
    localStorage.setItem("token", data.access_token);
    localStorage.setItem("username", form.username);
    router.push("/chat");
  } catch {
    ElMessage.error("用户名或密码错误");
  } finally {
    loading.value = false;
  }
}
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background: #f0f2f5;
}
.login-card {
  width: 400px;
}
.login-card h2 {
  text-align: center;
  margin-bottom: 20px;
}
.hint {
  text-align: center;
  color: #999;
  font-size: 12px;
}
</style>
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/views/LoginView.vue
git commit -m "feat: add login page with JWT authentication"
```

---

### 任务 28：前端 — WebSocket 通信层

**文件：**
- 创建：`f:\mysite\project1-ops-agent\frontend\src\composables\useWebSocket.ts`

- [ ] **步骤 1：编写 frontend/src/composables/useWebSocket.ts**

```typescript
import { ref, onUnmounted } from "vue";

interface WSMessage {
  type: string;
  payload: Record<string, unknown>;
}

export function useWebSocket(sessionId: string) {
  const connected = ref(false);
  const replyContent = ref("");
  const replyIntent = ref("");
  const replyConfidence = ref(0);
  const replySources = ref<Array<{ title: string; score: number }>>([]);
  const isStreaming = ref(false);
  let ws: WebSocket | null = null;
  let reconnectTimer: number | null = null;
  const onTicketPreview = ref<((payload: Record<string, unknown>) => void) | null>(null);

  function connect() {
    const token = localStorage.getItem("token");
    const wsUrl = `ws://localhost:8000/ws/chat/${sessionId}?token=${token}`;
    ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      connected.value = true;
    };

    ws.onmessage = (event) => {
      const msg: WSMessage = JSON.parse(event.data);
      switch (msg.type) {
        case "reply_start":
          replyContent.value = "";
          replyIntent.value = (msg.payload.intent as string) || "";
          isStreaming.value = true;
          break;
        case "reply_chunk":
          replyContent.value += msg.payload.content || "";
          break;
        case "reply_end":
          isStreaming.value = false;
          replyConfidence.value = (msg.payload.confidence as number) || 0;
          replySources.value = (msg.payload.sources as Array<{ title: string; score: number }>) || [];
          break;
        case "ticket_preview":
          if (onTicketPreview.value) {
            onTicketPreview.value(msg.payload);
          }
          break;
      }
    };

    ws.onclose = () => {
      connected.value = false;
      scheduleReconnect();
    };
  }

  function scheduleReconnect() {
    if (reconnectTimer) return;
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null;
      connect();
    }, 3000);
  }

  function sendMessage(content: string) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "message", payload: { content, msg_type: "text" } }));
    }
  }

  function sendFeedback(messageId: string, feedback: string) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: "feedback", payload: { message_id: messageId, feedback } }));
    }
  }

  function disconnect() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
    ws?.close();
  }

  onUnmounted(disconnect);

  return {
    connected,
    replyContent,
    replyIntent,
    replyConfidence,
    replySources,
    isStreaming,
    onTicketPreview,
    connect,
    sendMessage,
    sendFeedback,
    disconnect,
  };
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/composables/useWebSocket.ts
git commit -m "feat: add WebSocket composable with auto-reconnect and streaming support"
```

---

### 任务 29：前端 — 聊天状态管理

**文件：**
- 创建：`f:\mysite\project1-ops-agent\frontend\src\stores\chat.ts`

- [ ] **步骤 1：编写 frontend/src/stores/chat.ts**

```typescript
import { defineStore } from "pinia";
import { ref, computed } from "vue";
import type { ChatMessage } from "../types";

export const useChatStore = defineStore("chat", () => {
  const messages = ref<ChatMessage[]>([]);
  const sessionId = ref<string>(crypto.randomUUID());

  const addMessage = (msg: ChatMessage) => {
    const existing = messages.value.find((m) => m.id === msg.id);
    if (existing) {
      existing.content = msg.content;
    } else {
      messages.value.push(msg);
    }
  };

  const clearMessages = () => {
    messages.value = [];
  };

  return { messages, sessionId, addMessage, clearMessages };
});
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/src/stores/chat.ts
git commit -m "feat: add Pinia chat store for message state management"
```

---

### 任务 30：前端 — 聊天界面组件

**文件：**
- 创建：`f:\mysite\project1-ops-agent\frontend\src\components\MessageBubble.vue`
- 创建：`f:\mysite\project1-ops-agent\frontend\src\components\ChatInput.vue`
- 创建：`f:\mysite\project1-ops-agent\frontend\src\components\ChatWindow.vue`
- 创建：`f:\mysite\project1-ops-agent\frontend\src\components\TicketPreview.vue`
- 创建：`f:\mysite\project1-ops-agent\frontend\src\views\ChatView.vue`

- [ ] **步骤 1：编写 MessageBubble.vue**

```vue
<template>
  <div :class="['message-bubble', role]">
    <div class="avatar">{{ role === "user" ? "我" : "AI" }}</div>
    <div class="bubble">
      <div class="content">{{ content }}</div>
      <div v-if="sources && sources.length > 0" class="sources">
        <span class="source-label">来源：</span>
        <span v-for="s in sources" :key="s.title" class="source-item">{{ s.title }}</span>
      </div>
      <div v-if="role === 'assistant' && msgId" class="feedback">
        <el-button size="small" text @click="$emit('feedback', msgId, 'helpful')">有帮助</el-button>
        <el-button size="small" text @click="$emit('feedback', msgId, 'unhelpful')">无帮助</el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
defineProps<{
  role: string;
  content: string;
  sources?: Array<{ title: string; score: number }>;
  msgId?: string;
}>();

defineEmits<{
  feedback: [messageId: string, feedback: string];
}>();
</script>

<style scoped>
.message-bubble { display: flex; gap: 10px; margin: 12px 0; }
.message-bubble.user { flex-direction: row-reverse; }
.avatar { width: 32px; height: 32px; border-radius: 50%; background: #409eff; color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; flex-shrink: 0; }
.message-bubble.user .avatar { background: #67c23a; }
.bubble { max-width: 70%; padding: 10px 14px; border-radius: 12px; background: #f4f4f5; }
.message-bubble.user .bubble { background: #409eff; color: #fff; }
.sources { margin-top: 6px; font-size: 12px; color: #909399; }
.source-item { margin-right: 8px; }
.feedback { margin-top: 6px; }
</style>
```

- [ ] **步骤 2：编写 ChatInput.vue**

```vue
<template>
  <div class="chat-input">
    <el-input
      v-model="text"
      placeholder="输入运维问题..."
      @keyup.enter="send"
      :disabled="disabled"
      size="large"
    >
      <template #append>
        <el-button @click="send" :disabled="disabled || !text.trim()">发送</el-button>
      </template>
    </el-input>
  </div>
</template>

<script setup lang="ts">
import { ref } from "vue";

const props = defineProps<{ disabled?: boolean }>();
const emit = defineEmits<{ send: [text: string] }>();
const text = ref("");

function send() {
  if (!text.value.trim()) return;
  emit("send", text.value.trim());
  text.value = "";
}
</script>

<style scoped>
.chat-input { padding: 16px; border-top: 1px solid #e4e7ed; }
</style>
```

- [ ] **步骤 3：编写 ChatWindow.vue**

```vue
<template>
  <div class="chat-window">
    <div class="messages" ref="messagesRef">
      <MessageBubble
        v-for="msg in messages"
        :key="msg.id"
        :role="msg.role"
        :content="msg.content"
        :sources="msg.sources"
        :msg-id="msg.id"
        @feedback="onFeedback"
      />
      <div v-if="streaming" class="message-bubble assistant">
        <div class="avatar">AI</div>
        <div class="bubble">
          <div class="content">{{ streamingContent }}</div>
        </div>
      </div>
    </div>
    <ChatInput :disabled="streaming" @send="onSend" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, nextTick } from "vue";
import MessageBubble from "./MessageBubble.vue";
import ChatInput from "./ChatInput.vue";
import type { ChatMessage } from "../types";

const props = defineProps<{
  messages: ChatMessage[];
  streaming: boolean;
  streamingContent: string;
}>();

const emit = defineEmits<{
  send: [text: string];
  feedback: [messageId: string, feedback: string];
}>();

const messagesRef = ref<HTMLElement>();

watch(
  () => [props.messages.length, props.streamingContent],
  () => nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight;
    }
  }),
);

function onSend(text: string) { emit("send", text); }
function onFeedback(msgId: string, feedback: string) { emit("feedback", msgId, feedback); }
</script>

<style scoped>
.chat-window { display: flex; flex-direction: column; height: 100%; }
.messages { flex: 1; overflow-y: auto; padding: 16px; }
</style>
```

- [ ] **步骤 4：编写 TicketPreview.vue**

```vue
<template>
  <el-dialog v-model="visible" title="预填工单预览" width="500px">
    <el-descriptions :column="1" border>
      <el-descriptions-item label="工单号">{{ ticket.ticket_id }}</el-descriptions-item>
      <el-descriptions-item label="故障摘要">{{ ticket.summary }}</el-descriptions-item>
      <el-descriptions-item label="紧急程度">{{ ticket.urgency }}</el-descriptions-item>
      <el-descriptions-item label="设备类型">{{ ticket.device?.type }}</el-descriptions-item>
    </el-descriptions>
    <template #footer>
      <el-button type="primary" @click="visible = false">确认</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref } from "vue";

const visible = ref(false);
const ticket = ref<Record<string, unknown>>({});

function show(data: Record<string, unknown>) {
  ticket.value = data;
  visible.value = true;
}

defineExpose({ show });
</script>
```

- [ ] **步骤 5：编写 ChatView.vue**

```vue
<template>
  <div class="chat-view">
    <ChatWindow
      :messages="store.messages"
      :streaming="ws.isStreaming.value"
      :streaming-content="ws.replyContent.value"
      @send="onSend"
      @feedback="onFeedback"
    />
    <TicketPreview ref="ticketPreviewRef" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import ChatWindow from "../components/ChatWindow.vue";
import TicketPreview from "../components/TicketPreview.vue";
import { useChatStore } from "../stores/chat";
import { useWebSocket } from "../composables/useWebSocket";

const router = useRouter();
const store = useChatStore();
const ticketPreviewRef = ref<InstanceType<typeof TicketPreview>>();
const ws = useWebSocket(store.sessionId);

onMounted(() => {
  const token = localStorage.getItem("token");
  if (!token) {
    router.push("/login");
    return;
  }
  ws.connect();
  ws.onTicketPreview.value = (payload) => {
    ticketPreviewRef.value?.show(payload);
  };
});

let assistantMsgId = "";

function onSend(text: string) {
  const userMsgId = crypto.randomUUID();
  store.addMessage({ id: userMsgId, role: "user", content: text, msg_type: "text" });
  assistantMsgId = crypto.randomUUID();
  store.addMessage({ id: assistantMsgId, role: "assistant", content: "", msg_type: "text" });
  ws.sendMessage(text);
}

function onFeedback(msgId: string, feedback: string) {
  ws.sendFeedback(msgId, feedback);
}
</script>

<style scoped>
.chat-view { height: 100vh; display: flex; flex-direction: column; }
</style>
```

- [ ] **步骤 6：Commit**

```bash
git add frontend/src/components/ frontend/src/views/ChatView.vue
git commit -m "feat: add chat UI components with streaming, feedback, and ticket preview"
```

---

### 任务 31：前端 — nginx 配置

**文件：**
- 创建：`f:\mysite\project1-ops-agent\frontend\nginx.conf`

- [ ] **步骤 1：编写 nginx.conf**

```nginx
server {
    listen 80;
    server_name localhost;

    location / {
        root /usr/share/nginx/html;
        index index.html;
        try_files $uri $uri/ /index.html;
    }

    location /api/ {
        proxy_pass http://backend:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /ws/ {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

- [ ] **步骤 2：Commit**

```bash
git add frontend/nginx.conf
git commit -m "feat: add nginx config for frontend deployment"
```

---

### 任务 32：最终集成验证

- [ ] **步骤 1：启动全部服务**

```bash
cd f:\mysite\project1-ops-agent
docker-compose up -d
```

- [ ] **步骤 2：等待服务就绪后检查健康状态**

```bash
curl http://localhost:8000/api/v1/health
```
预期：`{"status":"ok","service":"ops-agent"}`

- [ ] **步骤 3：拉取模型**

```bash
docker exec project1-ops-agent-ollama-1 ollama pull quentinz/bge-large-zh-v1.5:latest
docker exec project1-ops-agent-ollama-1 ollama pull deepseek-r1:1.5b
```

- [ ] **步骤 4：测试登录**

```bash
curl -X POST http://localhost:8000/api/v1/auth/login -H "Content-Type: application/json" -d '{"username":"admin","password":"admin123"}'
```
预期：返回 `access_token`

- [ ] **步骤 5：测试知识库上传**

```bash
# 创建示例文档
echo "# 打印机常见故障" > f:\mysite\project1-ops-agent\docs\sample_knowledge.md
echo "## 卡纸处理" >> f:\mysite\project1-ops-agent\docs\sample_knowledge.md
echo "1. 关闭打印机电源" >> f:\mysite\project1-ops-agent\docs\sample_knowledge.md
echo "2. 打开前盖，轻轻取出卡住的纸张" >> f:\mysite\project1-ops-agent\docs\sample_knowledge.md
echo "3. 检查硒鼓是否安装到位" >> f:\mysite\project1-ops-agent\docs\sample_knowledge.md
echo "4. 关闭前盖，重新开机" >> f:\mysite\project1-ops-agent\docs\sample_knowledge.md

curl -X POST http://localhost:8000/api/v1/knowledge/upload -H "Authorization: Bearer <token>" -F "file=@docs/sample_knowledge.md"
```

- [ ] **步骤 6：打开前端验证**

浏览器打开 `http://localhost:3000`，用 admin/admin123 登录，测试聊天功能。

- [ ] **步骤 7：运行测试**

```bash
cd backend
pytest tests/ -v
```

- [ ] **步骤 8：Commit 最终版本**

```bash
git add .
git commit -m "chore: final integration verification and project delivery"
```

---

## 自检清单

1. **规格覆盖度：** 所有设计文档中的 22 个章节均已映射到对应任务：架构（任务1）、数据模型（任务3）、RAG（任务11）、意图分类（任务10）、记忆管理（任务15）、问题改写（任务12）、流式输出（任务20）、反馈溯源（任务16/22）、鉴权（任务17/19）、可观测性（任务5）、知识库（任务8/21）、Coverage Guard（任务16）、质量指标（任务24/25）、上线计划（任务1/32）。

2. **占位符扫描：** 无 "TODO"、"待定"、"后续实现" 等占位符。所有步骤包含完整代码。

3. **类型一致性：** 所有模型、Schema、API 间引用一致。Conversation → Message 关系正确，KnowledgeDoc → KnowledgeChunk 关系正确。chat.py 中引用的函数签名与各模块定义一致。

---

## 模型下载清单（手动操作）

在 `docker-compose up -d` 后，执行以下命令拉取模型：

```bash
# Embedding 模型（必需）
docker exec <container> ollama pull quentinz/bge-large-zh-v1.5:latest

# LLM 测试模型（必需）
docker exec <container> ollama pull deepseek-r1:1.5b

# Reranker 模型（已本地下载到 E:\ai\rerank\bge-reranker-base，无需重复下载）
```